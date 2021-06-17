# [START gae_flex_storage_app]
import logging
import os
import psycopg2
from flask import Flask, request, render_template, jsonify, Response, redirect, url_for, send_file
from google.cloud import storage
import io
from hurry.filesize import size, si
import librosa
import librosa.display
from matplotlib import pyplot, backends

app = Flask(__name__)

# Configure this environment variable via app.yaml
# CLOUD_STORAGE_BUCKET = os.environ['CLOUD_STORAGE_BUCKET']
# DB_USER = os.environ['DB_USER']
# DB_PASS = os.environ['DB_PASS']
# DB_NAME = os.environ['DB_NAME']
# DB_HOST = os.environ['DB_HOST']
# DB_PORT = os.environ['DB_PORT']

CLOUD_STORAGE_BUCKET = 'fc-n5-audio-process'
DB_USER = 'eyogyeoo'
DB_PASS = 'uENjChCcsy4fh4UGMziwwR--fq3qXq1r'
DB_NAME = 'eyogyeoo'
DB_HOST = 'batyr.db.elephantsql.com'
DB_PORT = '5432'
os.environ["GOOGLE_APPLICATION_CREDENTIALS"]="storage\credentials.json"

@app.route('/process/<string:blobName>', methods=['GET'])
def process_blob(blobName):
    gcs = storage.Client()
    bucket = gcs.get_bucket(CLOUD_STORAGE_BUCKET)
    all_blobs = gcs.list_blobs(bucket, delimiter="/")
    data = list_blobs()
    for search in all_blobs:
        if search.name == blobName:
            file_as_string = search.download_as_string()
            fig = graph2(io.BytesIO(file_as_string))
            output = io.BytesIO()
            backends.backend_agg.FigureCanvasAgg(fig).print_png(output)
            return Response(output.getvalue(), mimetype="image/png")
            
    return jsonify({'error': 'data not found'})

@app.route('/getprocess/<string:blobName>', methods=['GET'])
def getprocess_blob(blobName):
    path= "/process/{}".format(blobName)
    data = list_blobs()
    return render_template('index.html', audios = data, plots = path, selName = blobName)


@app.route('/process', methods=['GET'])
def process_audio():
    fig = graph()
    output = io.BytesIO()
    backends.backend_agg.FigureCanvasAgg(fig).print_png(output)
    return Response(output.getvalue(), mimetype="image/png")

def graph2(filename):
    y, sr = librosa.load(filename)
    y = y[:100000]  # shorten audio a bit for speed
    fig = pyplot.Figure()
    ax = fig.add_subplot(111)
    p = librosa.display.waveplot(y= y, sr =sr, ax=ax)
    return fig

def graph():
    filename = librosa.util.example_audio_file()
    y, sr = librosa.load(filename)
    y = y[:100000]  # shorten audio a bit for speed
    fig = pyplot.Figure()
    ax = fig.add_subplot(111)
    p = librosa.display.waveplot(y= y, sr =sr, ax=ax)
    return fig




@app.route('/')
def index():
    data = list_blobs()
    return render_template('index.html', audios = data, plots = False)

@app.route('/upload', methods=['POST'])
def upload():
    """Process the uploaded file and upload it to Google Cloud Storage."""
    uploaded_file = request.files.get('file')
    if not uploaded_file:
        return 'No file uploaded.', 400
    gcs = storage.Client()
    bucket = gcs.get_bucket(CLOUD_STORAGE_BUCKET)
    blob = bucket.blob(uploaded_file.filename)

    blob.upload_from_string(
        uploaded_file.read(),
        content_type=uploaded_file.content_type
    )
    insertTable(blob)
    # The public URL can be used to directly access the uploaded file via HTTP.
    return redirect(url_for('index'))


@app.route('/list', methods=['GET'])
def list_blobs():
    gcs = storage.Client()
    bucket = gcs.get_bucket(CLOUD_STORAGE_BUCKET)
    all_blobs = list(gcs.list_blobs(bucket, delimiter="/"))
    blobs = parseBlobs(all_blobs)
    return blobs

@app.route('/list/<string:blobName>', methods=['GET'])
def get_blob(blobName):
    gcs = storage.Client()
    bucket = gcs.get_bucket(CLOUD_STORAGE_BUCKET)
    all_blobs = list(gcs.list_blobs(bucket, delimiter="/"))
    blobs = parseBlobs(all_blobs)
    for search in blobs:
        if search['name'] == blobName:
            return jsonify(search)
    return jsonify({'error': 'data not found'})

def parseBlobs(listBlob):
    blobs = []
    for blob in listBlob:
        blobs.append(
            {
                'time_created': blob.time_created,
                'path': blob.path,
                'public_url': blob.public_url,
                'self_link': blob.self_link,
                'size': size(blob.size, system=si),
                'bucket': blob.bucket.name,
                'name': blob.name,
                'id': blob.id,
            })
    return blobs

def insertTable(blob):
    try:
        connection = psycopg2.connect(user=DB_USER,
                                      password=DB_PASS,
                                      host=DB_HOST,
                                      port=DB_PORT,
                                      database=DB_NAME)
        cursor = connection.cursor()

        postgres_insert_query = """ INSERT INTO blobs (name, bucket, path, time_created) VALUES (%s,%s,%s,%s)"""
        record_to_insert = (blob.name, blob.bucket.name, blob.path, blob.time_created)
        cursor.execute(postgres_insert_query, record_to_insert)

        connection.commit()
        count = cursor.rowcount
        print(count, "Record inserted successfully into mobile table")

    except (Exception, psycopg2.Error) as error:
        print("Failed to insert record into mobile table", error)

    finally:
        # closing database connection.
        if connection:
            cursor.close()
            connection.close()
            print("PostgreSQL connection is closed")

@app.errorhandler(500)
def server_error(e):
    logging.exception('An error occurred during a request.')
    return """
    An internal error occurred: <pre>{}</pre>
    See logs for full stacktrace.
    """.format(e), 500


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8080, debug=True)

