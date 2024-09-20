import concurrent.futures
from flask import Flask, request
from requests import get, exceptions as req_exceptions
from dns import resolver
from os import getenv
from signal import raise_signal, SIGINT
from socket import gethostname
from yaml import dump
from time import time
from argparse import ArgumentParser

app = Flask(__name__)

# get the host and port from the environment
HOSTNAME = gethostname()
STARTUP_TIME = time()

# Configure the version file
try:
    with open("/app/BUILD", "r") as f:
        version_file = f.readlines()
except FileNotFoundError:
    version_file = ["Dev (Runtime)", ""]

VERSION = version_file[0].strip()
VERSION_DATE = version_file[1].strip()

# Try to get the Kubernetes namespace
try:
    with open("/var/run/secrets/kubernetes.io/serviceaccount/namespace", "r") as f:
        NAMESPACE = f.read().strip()
except FileNotFoundError:
    NAMESPACE = None
    print(" * No Kubernetes namespace found - disabling SRV record lookup")

calls = 0
ready = True
alive = True

parser = ArgumentParser(prog='kube-demo-tool', description='A tool to for demonstrate and test some Kubernetes features.')
parser.add_argument('--host', help='The host to bind the service to.', default=getenv("HOST", "0.0.0.0"))
parser.add_argument('--port', help='The port to bind the service to.', default=getenv("PORT", "8080"))
parser.add_argument('--storage', help="Specify a path to enable the storage feature.", default=None)

args = parser.parse_args()

HOST = args.host
PORT = int(args.port)
STORAGE_PATH = args.storage


# Fetch a node from the SRV record
def fetchNode(srv):
    url = f"http://{srv.target.to_text()}:{srv.port}/me?ignore"
    response = get(url, timeout=0.5)
    if response.status_code == 200:
        return response.json()
    return None


# Get the others nodes from SRV records
def getNodes():
    out = []
    if NAMESPACE is None:
        return out

    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = {executor.submit(fetchNode, srv): srv for srv in resolver.resolve(f"http.tcp.demo-headless.{NAMESPACE}.svc.cluster.local", "SRV", lifetime=.5)}

        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result is not None:
                out.append(result)

    return out


def prepareStorage():
    if STORAGE_PATH is not None:
        try:
            with open(STORAGE_PATH, "a") as f:
                f.write(f"Started at {STARTUP_TIME} with version {VERSION}\n")
                f.close()
        except FileNotFoundError:
            with open(STORAGE_PATH, "w") as f:
                f.write(f"Started at {STARTUP_TIME} with version {VERSION}\n")
                f.close()
        except Exception as e:
            print(f" * Error while preparing storage: {e}")
            exit(1)


# Health endpoint - ready
@app.route("/healthz/ready")
def readyness():
    if ready:
        return {
            "hostname": HOSTNAME,
            "status": "Ready",
        }, 200

    return {
        "hostname": HOSTNAME,
        "status": "Not Ready",
    }, 503


# Health endpoint - alive
@app.route("/healthz/alive")
def liveness():
    if alive:
        return {
            "hostname": HOSTNAME,
            "status": "Alive",
        }, 200

    return {
        "hostname": HOSTNAME,
        "status": "Dead",
    }, 503


# Toggle endpoint ready/unready
@app.route("/ready")
def toggle_ready():
    global ready
    ready = not ready

    if ready:
        return {
            "hostname": HOSTNAME,
            "New Status": "Ready",
        }

    return {
        "hostname": HOSTNAME,
        "New Status": "Not Ready",
    }


# Toggle endpoint healthy/unhealthy
@app.route("/alive")
def toggle_alive():
    global alive, ready
    alive = not alive
    ready = alive

    if alive:
        return {
            "hostname": HOSTNAME,
            "New Status": "Healthy",
        }

    return {
        "hostname": HOSTNAME,
        "New Status": "Unhealthy",
    }


# Kill endpoint - kill the app
@app.route("/kill")
def kill():
    raise_signal(SIGINT)
    return {
        "hostname": HOSTNAME,
        "status": "Killing...",
    }


# Status endpoint
@app.route("/me")
def hello():
    if "ignore" not in request.args:
        global calls
        calls += 1

    ret_data = {
        "hostname": HOSTNAME,
        "calls": calls,
        "version": VERSION,
        "uptime": time() - STARTUP_TIME,
    }

    # Read the last line from the storage file
    if STORAGE_PATH is not None:
        with open(STORAGE_PATH, "r") as f:
            data = f.readlines()
            ret_data["last_line"] = data[-1].strip()

    return ret_data


@app.route("/")
def config():
    if "ignore" not in request.args:
        global calls
        calls += 1

    response = {
        "hostname": HOSTNAME,
        "calls": calls,
        "namespace": NAMESPACE,
        "build": {
            "version": VERSION,
            "date": VERSION_DATE
        },
        "status": {
            "alive": alive,
            "ready": ready,
        },
        "error": {}
    }

    try:
        response["nodes"] = getNodes()
    except resolver.NXDOMAIN:
        response["error"]["dns"] = "No SRV records found"
    except resolver.LifetimeTimeout:
        response["error"]["dns"] = "DNS Timeout"
    except req_exceptions.ConnectTimeout as e:
        response["error"]["req"] = "Connection Timeout"
    except Exception as e:
        response["error"]["other"] = f'[{e.__class__}] {str(e)}'

    return dump(response), 200, {"Content-Type": "application/json"}


@app.route("/sync-test")
def sync_test():
    # If the data test is not enabled, return 500
    if STORAGE_PATH is None:
        return {"error": "Data test is not enabled"}, 500

    request_time = time()

    # Write the data to the file
    with open(STORAGE_PATH, "a") as f:
        f.write(f"Request at {request_time}\n")
        f.close()

    # Read the data from the others nodes in parallel
    data = getNodes()

    response_time = time() - request_time

    # Get only the last line from the other nodes
    response = {}
    for node in data:
        if "last_line" not in node:
            response[node["hostname"]] = "No data"
        elif node["last_line"] != "Request at " + str(request_time):
            response[node["hostname"]] = "Out of sync"
        else:
            response[node["hostname"]] = "In sync"

    response["response_time"] = response_time

    return dump(response), 200, {"Content-Type": "application/json"}


if __name__ == "__main__":
    print(f" * Using Kubernetes Namespace: {NAMESPACE}")
    if STORAGE_PATH is not None:
        print(f" * Using Storage Path: {STORAGE_PATH}")
        prepareStorage()
    app.run(host=HOST, port=PORT)
