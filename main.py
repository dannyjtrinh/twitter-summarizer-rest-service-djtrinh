import threading
import time
import queue
import glob
import os
import os.path
import media_creator
import twitter_api as twit
import datetime
import subprocess
from flask import Flask, request, render_template, flash, request, render_template_string
from flask_restful import reqparse, abort, Api, Resource
from wtforms import Form, validators, StringField


app = Flask(__name__)
api = Api(app)
app.config.from_object(__name__)
app.config['SECRET_KEY'] = 'alsdjflaksdfaslkdj2942349'

# create queue
q1 = queue.Queue(maxsize=4)
q2 = queue.Queue()

TODOS = {
    'user': {'id': 'Generate images and video based off provided id'},
}


def abort_if_todo_doesnt_exist(todo_id):
    if todo_id not in TODOS:
        abort(404, message="Todo {} doesn't exist".format(todo_id))


parser = reqparse.RequestParser()
parser.add_argument('task')


class video_restful(Resource):
    def get(self, todo_id):
        return TODOS

    def put(self, todo_id):
        if todo_id == "name":
            username = request.form['user']
            if username != '':
                # Remove old pictures with matching Twitter ID
                filelist = glob.glob(os.path.join(r'processed_imgs/', username + "*.png"))
                if len(filelist) > 0:
                    for f in filelist:
                        os.remove(f)
                # Create processes to start generating pictures
                q_item = [username, twit.get_user_pic(username), twit.get_users_tweets(username)]
                t = threading.Thread(name="ProducerThread", target=producer, args=(q1, q_item))
                date_time = str(datetime.date.today()).replace('-', '_')
                q2.put([username, date_time])
                t.start()
                return "Running video creater with final video at 3.19.22.162/video/twitter_feed_" + username + '_' + date_time + '.mp4', 200
            else:
                return "Please enter a valid ID", 400
        elif todo_id == 'status':
            filename = request.form['filename']
            if not os.path.isfile('/home/ubuntu/flaskapp/static/' + filename):
                return "Video is still processing", 400
            else:
                if os.path.getsize('/home/ubuntu/flaskapp/static/' + filename) >= 100000:
                    return "Video is done", 400
                else:
                    return "Video is still processing", 400


class ReusableForm(Form):
    name = StringField('Name:', validators=[validators.DataRequired()])


@app.route("/", methods=['GET', 'POST'])
def home():
    form = ReusableForm(request.form)

    if request.method == 'POST':
        name=request.form['name']

        if form.validate():
            r = subprocess.check_output(['curl', '-d', 'user='+name, 'http://127.0.0.1/user/name', '-X', 'PUT'])
            return render_template_string('{{text}}', text=r)
        else:
            flash('Error: All Fields are Required')

    return render_template('index.html', form=form)


# Multimedia playback is better to not be restful
@app.route("/video/<name>")
def play_video(name):
    name = name.strip()
    if not os.path.isfile('/home/ubuntu/flaskapp/static/' + name):
        return "Video is still processing", 400
    else:
        if os.path.getsize('/home/ubuntu/flaskapp/static/' + name) >= 100000:
            html = f"""
            <!doctype html>
                <html>
                    <body>
                        <center>
                            <video width="768" controls>
                            <source src="/static/{name}" type="video/mp4">
                            </video>
                        </center>
                    </body>
                 </html>
           """
        else:
            return "Video is still processing", 400

    return html, 200



api.add_resource(video_restful, '/user/<todo_id>')


# Thread that processes create image requests. 4 of these are run
def processor(q, mc):
    while (True):
        item = q.get()
        # Do not create image item grabbed is blank
        if item is not None:
            mc.create_images(item[0], item[1], item[2], item[3])
            today = str(datetime.datetime.now())
            log = open("log_file.txt", 'a')
            log.write(today + ": " + str(item[0]) + " image processing in progress...\n")
            log.close()
        q.task_done()
        time.sleep(.001)


# ffmpeg subprocess thread function that calls ffmpeg when files are ready
def ffpmeg_processor(q2, mc):
    while (True):
        q2_item = q2.get()
        username = q2_item[0]
        date_time = q2_item[1]
        # Do not check for images if username is blank
        if username is not None:
            png_count = len(glob.glob1(r"processed_imgs/", username + r"*.png"))
            today = str(datetime.datetime.now())

            if png_count < 20:
                q2.put(q2_item)
            else:
                log = open("log_file.txt", 'a')
                log.write(today + ": " + username + " video processing in progress...\n")
                log.close()
                mc.ffmpeg_call(username, date_time)
        q2.task_done()
        time.sleep(.001)


# thread function that puts creation of image task to the queue
def producer(q, q_item):
    # the main thread will put new items to the queue
    for count, tweet in enumerate(q_item[2]):
        q.put([q_item[0], q_item[1], tweet, count])
    q.join()


if __name__ == '__main__':
    # create media class which has functions that create images and videos
    mc = media_creator.media_creator()

    # grab keys
    twit = twit.twitter_scrapper("keys")

    # 4 threads to do processes running at .001 seconds . This will create the images
    threads_num = 4
    for i in range(threads_num):
        t = threading.Thread(name="Thread Processor-" + str(i), target=processor, args=(q1, mc,))
        t.start()

    # FFMPEG thread
    # Checks if images are there and creates the mp4 file if the criteria is met
    t = threading.Thread(name="FFMPEG Processor", target=ffpmeg_processor, args=(q2, mc,))
    t.start()

    # Flask
    app.run(host="0.0.0.0", port=80)
