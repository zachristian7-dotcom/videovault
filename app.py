from flask import Flask, render_template, request, redirect, url_for, send_from_directory
import os
import json
from werkzeug.utils import secure_filename
from datetime import datetime
import cv2

app = Flask(__name__)

UPLOAD_FOLDER = "static/uploads"
THUMB_FOLDER = "static/thumbs"
DATA_FILE = "videos.json"

ALLOWED_EXTENSIONS = {"mp4", "webm", "mov"}
MAX_FILE_SIZE_MB = 500


# Make sure folders exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(THUMB_FOLDER, exist_ok=True)

# Create json if missing
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump([], f)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def load_videos():
    with open(DATA_FILE, "r") as f:
        return json.load(f)


def save_videos(videos):
    with open(DATA_FILE, "w") as f:
        json.dump(videos, f, indent=4)


def pretty_date(iso):
    dt = datetime.fromisoformat(iso)
    return dt.strftime("%b %d, %Y - %I:%M %p")


def generate_thumbnail(video_path, thumb_path):
    cap = cv2.VideoCapture(video_path)
    success, frame = cap.read()
    cap.release()

    if success:
        cv2.imwrite(thumb_path, frame)
        return True
    return False


@app.route("/")
def index():
    videos = load_videos()

    search = request.args.get("search", "").lower()
    sort = request.args.get("sort", "newest")

    # Add pretty date
    for v in videos:
        v["pretty_date"] = pretty_date(v["uploaded_at"])

    # Filter by search
    if search:
        videos = [
            v for v in videos
            if search in v["title"].lower()
            or search in v["description"].lower()
            or search in v["filename"].lower()
        ]

    # Sort
    if sort == "newest":
        videos.sort(key=lambda x: x["uploaded_at"], reverse=True)
    elif sort == "oldest":
        videos.sort(key=lambda x: x["uploaded_at"])
    elif sort == "views":
        videos.sort(key=lambda x: x["views"], reverse=True)
    elif sort == "hearts":
        videos.sort(key=lambda x: x["hearts"], reverse=True)

    playlists = sorted(list(set([v["playlist"] for v in videos if v.get("playlist")])))

    return render_template("index.html", videos=videos, playlists=playlists, search=search, sort=sort)


@app.route("/playlist/<playlist_name>")
def playlist_page(playlist_name):
    videos = load_videos()

    filtered = [v for v in videos if v.get("playlist") == playlist_name]

    for v in filtered:
        v["pretty_date"] = pretty_date(v["uploaded_at"])

    filtered.sort(key=lambda x: x["uploaded_at"], reverse=True)

    return render_template("playlist.html", videos=filtered, playlist_name=playlist_name)


@app.route("/upload", methods=["GET", "POST"])
def upload():
    if request.method == "POST":
        if "video" not in request.files:
            return "No file uploaded."

        file = request.files["video"]

        if file.filename == "":
            return "No selected file."

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)

            base, ext = os.path.splitext(filename)
            counter = 1
            while os.path.exists(os.path.join(UPLOAD_FOLDER, filename)):
                filename = f"{base}_{counter}{ext}"
                counter += 1

            filepath = os.path.join(UPLOAD_FOLDER, filename)

            # Check file size
            file.seek(0, os.SEEK_END)
            size_mb = file.tell() / (1024 * 1024)
            file.seek(0)

            if size_mb > MAX_FILE_SIZE_MB:
                return f"File too large. Max {MAX_FILE_SIZE_MB}MB."

            file.save(filepath)

            title = request.form.get("title", "").strip()
            description = request.form.get("description", "").strip()
            playlist = request.form.get("playlist", "").strip()

            if title == "":
                title = filename

            # Create thumbnail
            thumb_name = filename.rsplit(".", 1)[0] + ".jpg"
            thumb_path = os.path.join(THUMB_FOLDER, thumb_name)

            if not generate_thumbnail(filepath, thumb_path):
                thumb_name = "default.jpg"

            videos = load_videos()
            videos.append({
                "filename": filename,
                "title": title,
                "description": description,
                "playlist": playlist,
                "thumbnail": thumb_name,
                "hearts": 0,
                "views": 0,
                "uploaded_at": datetime.now().isoformat()
            })

            save_videos(videos)

            return redirect(url_for("index"))

        return "Invalid file type."

    return render_template("upload.html")


@app.route("/heart/<filename>", methods=["POST"])
def heart(filename):
    videos = load_videos()

    for v in videos:
        if v["filename"] == filename:
            v["hearts"] += 1
            break

    save_videos(videos)
    return redirect(url_for("index"))


@app.route("/view/<filename>", methods=["POST"])
def view(filename):
    videos = load_videos()

    for v in videos:
        if v["filename"] == filename:
            v["views"] += 1
            break

    save_videos(videos)
    return ("", 204)


@app.route("/delete/<filename>", methods=["POST"])
def delete(filename):
    videos = load_videos()

    deleted_video = None
    new_list = []

    for v in videos:
        if v["filename"] == filename:
            deleted_video = v
        else:
            new_list.append(v)

    save_videos(new_list)

    # Delete the video file
    video_path = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.exists(video_path):
        os.remove(video_path)

    # Delete the thumbnail file
    if deleted_video:
        thumb_path = os.path.join(THUMB_FOLDER, deleted_video["thumbnail"])
        if os.path.exists(thumb_path) and deleted_video["thumbnail"] != "default.jpg":
            os.remove(thumb_path)

    return redirect(url_for("index"))


@app.route("/download/<filename>")
def download(filename):
    return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)


if __name__ == "__main__":
    # Render uses PORT environment variable
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)