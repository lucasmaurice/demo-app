from flask import Flask, request
from requests import get, exceptions as req_exceptions
from dns import resolver
from os import getenv
from signal import raise_signal, SIGINT
from socket import gethostname
from yaml import dump
from time import time

app = Flask(__name__)

# get the host and port from the environment
HOST = getenv("HOST", "0.0.0.0")
PORT = int(getenv("PORT", "8080"))
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


# Get the others nodes from SRV records
def getNodes():
    out = []
    if NAMESPACE is None:
        return out

    for srv in resolver.resolve(f"http.tcp.demo-headless.{NAMESPACE}.svc.cluster.local", "SRV", lifetime=.5):
        print(f" * Found SRV record: {srv.target.to_text()}:{srv.port}")
        data = get("http://" + srv.target.to_text() + ":" + str(srv.port) + "/me?ignore", timeout=.5)
        if data.status_code == 200:
            out.append(data.json())

    return out


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

    return {
        "hostname": HOSTNAME,
        "calls": calls,
        "version": VERSION,
        "uptime": time() - STARTUP_TIME,
    }


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


if __name__ == "__main__":
    print(f" * Using Kubernetes Namespace: {NAMESPACE}")
    app.run(host=HOST, port=PORT)
