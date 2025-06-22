# filenames across projects needs to be unique, this scripts ensures that this is the case, and renames if necessary
import os
import glob


files = glob.glob("data/unsolved/**/*.json", recursive=True)
files = [file.replace("data/unsolved/", "") for file in files]

for i, file in enumerate(files):
    for j, file2 in enumerate(files[i + 1:]):
        file_stripped = "/".join(file.split("/")[1:])
        file2_stripped = "/".join(file2.split("/")[1:])
        if file_stripped == file2_stripped:
            new_file = os.path.dirname(file2) + "/" + os.path.basename(file2).replace(".json", f"_2.json")
            print(f"Renaming {file2} to {new_file}")
            os.rename(os.path.join("data/unsolved", file2), os.path.join("data/unsolved", new_file))
            files[i + 1 + j] = new_file