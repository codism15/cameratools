import argparse
import cv2
import numpy as np
import yaml

parser = argparse.ArgumentParser()
parser.add_argument('file', help='video file to be scanned')
parser.add_argument('-l', '--loglevel', dest='loglevel', action='store', metavar='L',
    default = "info", help = 'specify log level, defalt to INFO')
args = parser.parse_args()

cap = cv2.VideoCapture(args.file)
video_width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)   # float
video_height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT) # float
fps = cap.get(cv2.CAP_PROP_FPS)

resize_width = 480
resize_height = 480

if resize_width/video_width <= resize_height/video_height:
    resize_factor = resize_width/video_width
    resize_height = int(video_height * resize_factor)
else:
    resize_factor = resize_height/video_height
    resize_width = int(video_width * resize_factor)

frame_count = 0
grid_size = 24

def mouse_event_handler(event, x, y, flags, param):
    global start_x, start_y
    if event == cv2.EVENT_LBUTTONDOWN:
        start_x = x
        start_y = y

while(1):
    ret, frame = cap.read()

    if not ret:
        break

    frame_count += 1

    img_resized = cv2.resize(frame, (0,0), fx=resize_factor, fy=resize_factor)

    debug_info = 'frame: %d' % (frame_count)
    cv2.putText(img_resized, debug_info, (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 0, 255))

    # output grid
    for x in xrange(grid_size, resize_width, grid_size):
        pt1 = (x, 0)
        pt2 = (x, resize_height)
        cv2.line(img_resized, pt1, pt2, (150, 0, 150))
    for y in xrange(grid_size, resize_height, grid_size):
        pt1 = (0, y)
        pt2 = (resize_width, y)
        cv2.line(img_resized, pt1, pt2, (150, 0, 150))

    cv2.imshow('frame', img_resized)
    key = cv2.waitKey(100000) & 0xff
    if key == 27:
        break
