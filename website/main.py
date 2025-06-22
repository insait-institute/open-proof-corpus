import json
import os
from flask import Flask, render_template, jsonify, request, abort, redirect, url_for
import json
import glob
import random
from datetime import datetime
from filelock import FileLock, Timeout
from pathlib import Path
import tempfile
import time

data_folder = "data"

app = Flask(__name__)

def _atomic_write(dest: Path, data) -> None:
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", dir=dest.parent, delete=False, encoding="utf‑8"
        ) as tmp:
            tmp_path = Path(tmp.name)
            json.dump(data, tmp, indent=4, ensure_ascii=False)
            tmp.flush()
            os.fsync(tmp.fileno())  # make sure bytes hit the disk before rename
        # Atomic replace – either the new file appears in full or not at all.
        os.replace(tmp_path, dest)
    finally:
        # In the rare event of an exception before replace() call, make sure we
        # do not leave the temporary file behind.
        if tmp_path and tmp_path.exists():
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:  # pragma: no cover – best effort cleanup
                pass


def safe_write_json(
    file_path: str | os.PathLike,
    data,
    retries: int = 10,
    delay: float = 1,
    lock_timeout: int = 10,
) -> None:
    dest = Path(file_path).expanduser().resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)  # ensure directory exists

    lock = FileLock(str(dest) + ".lock", timeout=lock_timeout)

    for attempt in range(retries + 1):  # initial try + N retries
        try:
            with lock:  # blocks up to lock_timeout seconds
                _atomic_write(dest, data)
            return  # success → we are done
        except Timeout:  # couldn’t get the lock in this attempt
            if attempt >= retries:
                return  # out of attempts → propagate
            time.sleep(delay)

def convert_filename(filename):
    # Remove the ".json" extension from the filename
    if filename.endswith(".json"):
        filename = filename[:-5]
    filename = filename.replace("_", " ")
    filename = filename.replace("/", ": ")
    return filename

def convert_filename_back(filename):
    # Add the ".json" extension back to the filename
    filename = filename.replace(": ", "/")
    filename = filename.replace(" ", "_")
    if not filename.endswith(".json"):
        filename = filename + ".json"
    return filename

def grading_is_finished(grading_scheme, grading, useless=False):
    if useless:
        return 2
    if grading is None:
        return 0
    if grading.get("no_feedback", False) or grading.get("long", False):
        return 2
    feedback_stuff = [grading_element.get("feedback") is None or grading_element.get("feedback") == "" for grading_element in grading["details"]]
    score_stuff = [grading_element.get("score") is None for grading_element in grading["details"]]
    if all(feedback_stuff) or all(score_stuff):
        return 0
    elif any(feedback_stuff) or any(score_stuff):
        return 1
    elif len(grading["details"]) != len(grading_scheme):
        return 1
    else:
        return 2

@app.route('/')
def start():
    return render_template("begin.html")

@app.route('/instructions/')
def instructions():
    return render_template("instructions.html")

@app.route('/problem-review/')
def review():
    return render_template("problem_review.html")


@app.route('/upload/', methods=['POST'])
def upload():
    # 1. Check if the post request has the file part
    #    'gradingFile' should be the 'name' attribute of your <input type="file"> in the HTML.
    if 'gradingFile' not in request.files:
        return jsonify({"status": "error", "message": "No file part in the request"}), 400
    
    file = request.files['gradingFile']
    
    # 2. If the user does not select a file, the browser submits an
    #    empty file without a filename.
    if file.filename == '':
        return jsonify({"status": "error", "message": "No selected file"}), 400
    
    if file:
        try:
            # 3. Read the file's content. file.read() returns bytes.
            file_contents_bytes = file.read()
            
            # 4. Decode the bytes to a string (assuming UTF-8 encoding for the JSON file)
            file_contents_string = file_contents_bytes.decode('utf-8')
            
            # 5. Parse the string content as JSON
            jsondata = json.loads(file_contents_string)
            
            # Now 'jsondata' contains the Python dictionary/list from the uploaded JSON file.
            # You can process it as needed.
            # For example, log it or use its values:
            # print(f"Received JSON data: {jsondata}")
            random_id = random.randint(0, 1000000)
            os.makedirs(os.path.join(data_folder, "problem_review"), exist_ok=True)
            safe_write_json(
                os.path.join(data_folder, "problem_review", f"{random_id}.json"),
                jsondata
            )

            return redirect(f'/problem-review/{random_id}')
            
        except json.JSONDecodeError:
            return jsonify({"status": "error", "message": "Invalid JSON format in the uploaded file."}), 400
        except UnicodeDecodeError:
            return jsonify({"status": "error", "message": "File does not seem to be UTF-8 encoded."}), 400
        except Exception as e:
            app.logger.error(f"An unexpected error occurred: {e}") # Good practice to log server errors
            return jsonify({"status": "error", "message": f"An unexpected error occurred: {str(e)}"}), 500
            
    return jsonify({"status": "error", "message": "Unknown error during file upload."}), 500

# NEW/MODIFIED Route to serve the interactive HTML page
@app.route('/problem-review/<string:file_id>')
def review_problem_set(file_id):
    problem_file_path = os.path.join("data/problem_review", f"{file_id}.json")
    try:
        with open(problem_file_path, 'r', encoding='utf-8') as f:
            problems_data = json.load(f)
        # Pass the entire list of problems and the file_id to the template
        return render_template('problem_review_main.html', 
                               problems_data=problems_data, 
                               file_id=file_id,
                               file_name=f"{file_id}.json")
    except FileNotFoundError:
        app.logger.error(f"Problem file not found: {problem_file_path}")
        return abort(404, description="Problem set file not found.")
    except json.JSONDecodeError:
        app.logger.error(f"Invalid JSON in file: {problem_file_path}")
        return abort(400, description="Cannot decode JSON from problem set file.")
    except Exception as e:
        app.logger.error(f"Error reading problem file {problem_file_path}: {e}")
        return abort(500, description="Error processing problem set file.")


# NEW Route to handle updates to a specific problem
@app.route('/update-problem/<string:file_id>/<int:problem_index>', methods=['POST'])
def update_problem(file_id, problem_index):
    problem_file_path = os.path.join("data/problem_review", f"{file_id}.json")
    try:
        # Get the updated data from the request
        updated_data = request.get_json()
        if not updated_data:
            return jsonify({"status": "error", "message": "No data provided for update."}), 400

        # Read the existing problems
        with open(problem_file_path, 'r', encoding='utf-8') as f:
            problems_list = json.load(f)

        if not isinstance(problems_list, list) or problem_index >= len(problems_list) or problem_index < 0:
            return jsonify({"status": "error", "message": "Invalid problem index or file format."}), 400

        # Update the specific problem
        # Only update fields that are present in updated_data
        if 'problem' in updated_data:
            problems_list[problem_index]['problem'] = updated_data['problem']
        if "delete" in updated_data:
            problems_list[problem_index]["delete"] = updated_data["delete"]
        
        problems_list[problem_index]["edited"] = True
        problems_list[problem_index]["edit_date"] = datetime.now().isoformat()

        # Write the entire modified list back to the file
        safe_write_json(
            problem_file_path,
            problems_list,
        )
        
        return jsonify({
            "status": "success", 
            "message": f"Problem {problem_index} in {file_id}.json updated.",
        })

    except FileNotFoundError:
        return jsonify({"status": "error", "message": "Problem set file not found."}), 404
    except json.JSONDecodeError:
        return jsonify({"status": "error", "message": "Error decoding JSON on server or in request."}), 400
    except Exception as e:
        app.logger.error(f"Error updating problem {file_id}/{problem_index}: {e}")
        return jsonify({"status": "error", "message": f"An unexpected error occurred: {str(e)}"}), 500


@app.route('/<judge_id>/')
def index(judge_id):
    file_names = glob.glob(os.path.join(data_folder, judge_id, "**/*.json"), recursive=True)
    if len(file_names) == 0:
        return render_template("404.html")
    else:
        return render_template("index.html")

@app.route('/<judge_id>/save_grading/', methods=['POST'])
def save_grading(judge_id):
    jsondata = request.get_json()
    file_name = convert_filename_back(jsondata["file_name"])
    file_path = os.path.join(data_folder, judge_id, file_name)
    if not os.path.exists(file_path):
        return jsonify({"status": "File not found"})
    with open(file_path, 'r') as f:
        data = json.load(f)
    # Update the grading information in the data
    grading = {
        "details": jsondata["data"],
        "score": sum([element["score"] for element in jsondata["data"] if element["score"] is not None]),
        "uncertain": jsondata["uncertain"].get("uncertain", "off") == "on",
        "no_feedback": jsondata["uncertain"].get("no_feedback", "off") == "on",
        "long": jsondata["uncertain"].get("long", "off") == "on",
    }
    if jsondata["annotation"]:
        if data["attempts"][jsondata["run_index"]].get("annotations") is None:
            data["attempts"][jsondata["run_index"]]["annotations"] = []
        already_exists = False
        for annotation in data["attempts"][jsondata["run_index"]]["annotations"]:
            annotation_no_id = annotation.copy()
            del annotation_no_id["id"]
            jsondata_annotation_no_id = jsondata["annotation"].copy()
            del jsondata_annotation_no_id["id"]
            if annotation_no_id == jsondata_annotation_no_id:
                already_exists = True
        if not already_exists:
            data["attempts"][jsondata["run_index"]]["annotations"].append(jsondata["annotation"])
    

    data["attempts"][jsondata["run_index"]]["grading"] = grading
    data["last_update"] = datetime.now().isoformat()
    # Save the updated data back to the file
    safe_write_json(
        file_path,
        data,
    )
    return jsonify({"status": "success"})

def let_others_know(file_name, issue, judge_id, run_index, is_problem):
    # Add problem to all other judges that have the same file
    for judge in os.listdir(data_folder):
        if judge == judge_id:
            continue
        file_path = os.path.join(data_folder, judge, file_name)
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                data = json.load(f)
            if is_problem:
                if issue:
                    data["issue_other_judge"] = {
                        "judge_id": judge_id,
                        "issue": issue,
                    }
                elif "issue_other_judge" in data and data["issue_other_judge"]["judge_id"] == judge_id:
                    del data["issue_other_judge"]
            else:
                if issue:
                    data["solutions"][run_index]["issue_other_judge"] = {
                        "judge_id": judge_id,
                        "issue": issue,
                    }
                elif "issue_other_judge" in data["solutions"][run_index] and data["solutions"][run_index]["issue_other_judge"]["judge_id"] == judge_id:
                    del data["solutions"][run_index]["issue_other_judge"]
            # Save the updated data back to the file
            safe_write_json(
                file_path,
                data,
            )


@app.route('/<judge_id>/report_problem/', methods=['POST'])
def report_problem(judge_id):
    jsondata = request.get_json()
    file_name = convert_filename_back(jsondata["file_name"])
    file_path = os.path.join(data_folder, judge_id, file_name)
    if not os.path.exists(file_path):
        return jsonify({"status": "File not found"})
    with open(file_path, 'r') as f:
        data = json.load(f)
    # Update the grading information in the data
    if jsondata["is_problem"]:
        data["issue"] = jsondata["description"]
        path = os.path.join(data_folder, "problems", file_name)
        data["useless"] = jsondata["useless"]

        if not os.path.exists(path) and data["issue"]:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            safe_write_json(
                path,
                data,
            )
        elif os.path.exists(path) and not data["issue"]:
            os.remove(path)
    else:
        data["solutions"][jsondata["run_index"]]["issue"] = jsondata["description"]
        path = os.path.join(data_folder, "solutions", file_name)
        if not os.path.exists(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            safe_write_json(
                path,
                data,
            )
        elif os.path.exists(path) and not data["solutions"][jsondata["run_index"]]["issue"]:
            os.remove(path)
    # Save the updated data back to the file
    safe_write_json(
        file_path,
        data,
    )

    let_others_know(file_name, jsondata["description"], judge_id, jsondata["run_index"], jsondata["is_problem"])
    
    data["last_update"] = datetime.now().isoformat()
    return jsonify({"status": "success"})

@app.route('/<judge_id>/remove_annotation/', methods=['POST'])
def remove_annotation(judge_id):
    jsondata = request.get_json()
    file_name = convert_filename_back(jsondata["file_name"])
    file_path = os.path.join(data_folder, judge_id, file_name)
    if not os.path.exists(file_path):
        return jsonify({"status": "File not found"})
    with open(file_path, 'r') as f:
        data = json.load(f)
    # Update the grading information in the data
    if data["attempts"][jsondata["run_index"]].get("annotations") is not None:
        for i, annotation in enumerate(data["attempts"][jsondata["run_index"]]["annotations"]):
            if annotation["id"] == jsondata["annotation_id"]:
                del data["attempts"][jsondata["run_index"]]["annotations"][i]
                break
    
    data["last_update"] = datetime.now().isoformat()
    # Save the updated data back to the file
    safe_write_json(
        file_path,
        data,
    )
    return jsonify({"status": "success"})


@app.route('/<judge_id>/llm_judge_feedback/', methods=['POST'])
def llm_judge_feedback(judge_id):
    jsondata = request.get_json()
    file_name = convert_filename_back(jsondata["file_name"])
    file_path = os.path.join(data_folder, judge_id, file_name)
    if not os.path.exists(file_path):
        return jsonify({"status": "File not found"})
    with open(file_path, 'r') as f:
        data = json.load(f)
    # Update the grading information in the data
    data["attempts"][jsondata["attemptIndex"]]["llm_judgment"]["result"]["issues"][jsondata["issueIndex"]]["accepted"] = jsondata["accepted"]
    
    data["last_update"] = datetime.now().isoformat()
    # Save the updated data back to the file
    safe_write_json(
        file_path,
        data,
    )
    return jsonify({"status": "success"})

@app.route('/<judge_id>/file_names/')
def get_file_names(judge_id):
    # remove extensions from file names
    file_names = glob.glob(os.path.join(data_folder, judge_id, "**/*.json"), recursive=True)
    file_names = [os.path.relpath(file_name, os.path.join(data_folder, judge_id)) for file_name in file_names]
    returned_file_names = [os.path.splitext(file_name)[0] for file_name in file_names]
    
    all_data = dict()

    for file_name in file_names:
        try:
            with open(os.path.join(data_folder, judge_id, file_name), 'r') as f:
                data = json.load(f)
            all_data[file_name] = data
        except Exception:
            continue
    # sort file names
    returned_file_names.sort()
    
    finished_information = [
        [grading_is_finished(all_data[file_name + ".json"]["grading_scheme"], attempt["grading"], 
                             all_data[file_name + ".json"].get("useless", False)) 
                for attempt in all_data[file_name + ".json"]["attempts"] 
                if attempt["grading"] is None or not attempt["grading"].get("auto_grade", False)]
        for file_name in returned_file_names
    ]
    dict_return = {
        "file_names": [convert_filename(file_name) for file_name in returned_file_names],
        "finished": finished_information
    }
    return jsonify(dict_return)

@app.route('/<judge_id>/data/<file_name>/')
def get_data(judge_id, file_name):
    file_path = os.path.join(data_folder, judge_id, convert_filename_back(file_name))
    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404

    with open(file_path, 'r') as f:
        data = json.load(f)
    data["attempts"] = [
        attempt for attempt in data["attempts"] if attempt["grading"] is None or not attempt["grading"].get("auto_grade", False)
    ]
    return jsonify(data)

# app name
@app.errorhandler(404)
# inbuilt function which takes error as parameter
def not_found(e):
# defining function
  return render_template("404.html")

if __name__ == '__main__':
    app.run(debug=True, port=5020)
