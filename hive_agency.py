import json
import sys
import os
import time
import hive

sys.path.append('/usr/local/lib/python2.7/site-packages')
from flask import Flask, Response, request
from flask import send_from_directory
import jsonpickle

solver = hive.Solver()


app = Flask(__name__, static_url_path='/Volumes/Sandbox/hive', static_folder='public')

@app.route('/api/hello', methods=['GET'])
def hello_handler():
    return Response(
        jsonpickle.encode(solver.hello()),
        mimetype='application/json',
        headers={
            'Cache-Control': 'no-cache',
            'Access-Control-Allow-Origin': '*'
        }
    )

@app.route('/api/propose', methods=['POST'])
def propose_cmd():
    jsonEncoder = HiveToJSON()
    jsonEncoder.addObject(solver.hello())
    return Response(
        jsonEncoder.encode(solver.hello()),
        mimetype='application/json',
        headers={
            'Cache-Control': 'no-cache',
            'Access-Control-Allow-Origin': '*'
        }
    )

if __name__ == '__main__':
    app.run(port=int(os.environ.get("PORT", 3000)), debug=True)
