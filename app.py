from flask import Flask, send_from_directory, request, render_template
from werkzeug import secure_filename
import rankmatch
import csv, os
from datetime import datetime
app = Flask(__name__, static_folder='assets')

@app.route('/')
def root():
    return render_template("index.html")

@app.route("/solve", methods=["POST"])
def solve():
    data = list(csv.reader(request.files['data'].read().splitlines()))
    events = list(csv.reader(request.files['events'].read().splitlines()))
    results, errors = rankmatch.rankMatch(events, data)

    results_file = secure_filename(request.files['data'].filename)
    results_file = "results/"+datetime.now().strftime("%y-%m-%d_%H-%M-%S_")+results_file
    with open(results_file, "w") as out:
    	writer = csv.writer(out)
    	for row in results:
    		writer.writerow(row)

    return render_template("results.html", errors=errors, results_file=results_file)

@app.route("/results/<csv>")
def results(csv):
	return send_from_directory("results", csv)

if __name__ == "__main__":
	if os.getcwd() == "/var/www":
    	app.run(host="0.0.0.0", port=80, debug=True)
	else:
    	app.run(debug=True)