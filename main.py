import threading
import time
import queue
import glob
import os
import os.path
import media_creator
import twitter_api as twit
import datetime
from flask import Flask
from flask_restful import Api

app = Flask(__name__)
api = Api(app)


# create queue
q1 = queue.Queue(maxsize=4)
q2 = queue.Queue()


@app.route("/")
def home():
    return "Test"


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


# function that serves the user
@app.route('/user/<username>')
def server(username):
    id = username
    if id != '':
        # Remove old pictures with matching Twitter ID
        filelist = glob.glob(os.path.join(r'processed_imgs/', id + "*.png"))
        if len(filelist) > 0:
            for f in filelist:
                os.remove(f)
        # Create processes to start generating pictures
        q_item = [id, twit.get_user_pic(id), twit.get_users_tweets(id)]
        t = threading.Thread(name="ProducerThread", target=producer, args=(q1, q_item))
        date_time = str(datetime.date.today()).replace('-', '_')
        q2.put([id, date_time])
        t.start()
        return "Running video creater with final video at http://127.0.0.1:5000/video/twitter_feed_"+ username + '_' + date_time + '.mp4', 200
    else:
        return "Please enter a valid ID", 400


@app.route('/video/<name>')
def play_video(name):
    name = name.strip()
    if not os.path.isfile(name):
        return "Video is still processing", 400

    html = f"""
        <center>
            <!doctype html>
            <html>
                <head>
                    <title>butterfly</title>
                </head>
                <body>
                    <video width="768" controls>
                        <source src="./../static/{name}" type="video/mp4">
                    </video>
                </body>
            </html>
        </center>
    """
    return html, 200


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

    app.run(debug=True)
