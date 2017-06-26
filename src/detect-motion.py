import numpy as np
import cv2
import sys
import time
import math
import argparse
import yaml
import logging
import os
from collections import deque

# parse command line
parser = argparse.ArgumentParser()
parser.add_argument('file', help='video file to be scanned')
parser.add_argument('-l', '--loglevel', dest='loglevel', action='store', metavar='L',
    default = "info", help = 'specify log level, defalt to INFO')

args = parser.parse_args()

# config logging
log_levels = {
    "info": logging.INFO,
    "debug": logging.DEBUG,
    "error": logging.ERROR,
    "warning": logging.WARN,
    "warn": logging.WARN
}

FORMAT = "%(asctime)s %(name)s %(levelname)s: %(message)s"
logging.basicConfig(format=FORMAT,
    datefmt = '%Y-%m-%dT%H:%M:%S',
    level = log_levels[args.loglevel.lower()], filename = '%s/log/detect-motion.log'%(os.path.expanduser('~')))

logging.info('== START')

# load the configuration

with open('detect-motion.yaml', 'r') as f:
    conf = yaml.safe_load(f)

class Tracer():
    def __init__(self, rect_list, frame_count = 1, missed_frame = 0):
        self.rectangles = []
        self.rectangles.extend(rect_list)
        self.frame_count = frame_count
        self.missed_frame = missed_frame
        self.area_variation = conf['tracer']['area_variation']

    def process_frame(self, rect_list):
        self.frame_count += 1
        x, y, w, h = self.rectangles[-1]
        area = w * h
        cx = x + w / 2
        cy = y + h / 2
        
        new_tracers = []
        
        for rect in rect_list:
            # test area similarity
            x1, y1, w1, h1 = rect
            area1 = w1 * h1
            area_variation = abs(float((area1 - area)) / area)
            if area_variation > self.area_variation:
                continue

            # test movement
            cx1 = x1 + w1 / 2
            cy1 = y1 + h1 / 2
            #d = int(math.sqrt((cx1 - cx) * (cx1 - cx) + (cy1 - cy) * (cy1 - cy)))
            d = (cx1 - cx) * (cx1 - cx) + (cy1 - cy) * (cy1 - cy)
            #print('distance: %d, area: %d'%(d, area))
            if d+d > area:
                continue
            
            new_tracer = Tracer(self.rectangles, self.frame_count, 0)
            new_tracer.rectangles.append(rect)

            new_tracers.append(new_tracer)
        
        if len(new_tracers) == 0:
            self.missed_frame += 1
            new_tracers.append(self)
        
        return new_tracers

def has_intersection(a, b):
    x = max(a[0], b[0])
    y = max(a[1], b[1])
    w = min(a[0]+a[2], b[0]+b[2]) - x
    h = min(a[1]+a[3], b[1]+b[3]) - y
    return w > 0 and h > 0

def merge_rect(a, b):
    x = min(a[0], b[0])
    y = min(a[1], b[1])
    w = max(a[0]+a[2], b[0]+b[2]) - x
    h = max(a[1]+a[3], b[1]+b[3]) - y
    return (x, y, w, h)

def merge_rectangles(rectangles, frame = None):
    # if frame is not None:
    #     img_temp = frame.copy()
    #user_pressed_esc = False
    g = 0
    
    while len(rectangles) > 1 and g < len(rectangles):
        rectangle_count_before = len(rectangles)
        # for idx, rect in enumerate(rectangles):
        #     x, y, w, h = rect
        #     cv2.rectangle(img_temp, (x, y), (x+w, y+h), (0, 0, 200), 1)
        merge_list = []
        x, y, w, h = rectangles[g]
        for idx in xrange(g+1, len(rectangles)):
            if has_intersection(rectangles[g], rectangles[idx]):
                merge_list.append(idx)
                x, y, w, h = merge_rect((x, y, w, h), rectangles[idx])
        if len(merge_list) > 0:
            rectangles[g] = (x, y, w, h)
            for idx in reversed(merge_list):
                del rectangles[idx]
        else:
            g += 1

        # debug
        # if img_temp is not None:
        #     debug_info = 'rectangles: %d/%d, g: %d' % (rectangle_count_before, len(rectangles), g)
        #     cv2.putText(img_temp, debug_info, (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 0, 255))
        #     for idx, rect in enumerate(rectangles):
        #         x, y, w, h = rect
        #         cv2.rectangle(img_temp, (x, y), (x+w, y+h), (0, 255, 0), 1)

        #     if not user_pressed_esc:
        #         cv2.imshow('frame', img_temp)
        #         k = cv2.waitKey(100000) & 0xff
        #         if k == 27:
        #             user_pressed_esc = True
        #     img_temp = frame.copy()

def get_resize_factor(video_width, video_height):
    resize_width = conf['resize_width']
    resize_height = conf['resize_height']
    if resize_width >= video_width and resize_height >= video_height:
        return 1.0
    width_factor = float(resize_width) / video_width
    height_factor = float(resize_width) / video_height
    resize_factor = min(width_factor, height_factor)
    return resize_factor

def get_rect_center(rect):
    x, y, w, h = rect
    return (x + w /2, y + h/2)

# load video
logging.info('loading %s', args.file)
cap = cv2.VideoCapture(args.file)
video_width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)   # float
video_height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT) # float
fps = cap.get(cv2.CAP_PROP_FPS)

logging.info('video info: %0.0fx%0.0f, fps: %d', video_width, video_height, fps)

resize_factor = get_resize_factor(video_width, video_height)
logging.debug('resize_factor: %f', resize_factor)

# load common settings into variables for fast access
threshold = conf['threshold']
dilate_iteration = conf['dilate_iteration']
contour_minimal_area = conf['contour_minimal_area']
no_gui = conf['no_gui']
tracer_frame_count = conf['tracer']['frame_count']
tracer_max_missed_frame = conf['tracer']['max_missed_frame']
tracer_distance = conf['tracer']['distance']
single_detection = conf['single_detection']

last_frame = None
tracers = []
frame_count = 0
motion_detected = False
while(1):
    ret, frame = cap.read()

    if not ret:
        break

    frame_count += 1

    #frame = cv2.GaussianBlur(frame, (5, 5), 0)
    img_resized = cv2.resize(frame, (0,0), fx=resize_factor, fy=resize_factor)
    img_gray = cv2.cvtColor(img_resized, cv2.COLOR_BGR2GRAY)

    if last_frame is None:
        last_frame = img_gray
        continue

    img_delta = cv2.absdiff(last_frame, img_gray)
    img_bw = cv2.threshold(img_delta, threshold, 255, cv2.THRESH_BINARY)[1]

    #img_bw = cv2.erode(img_bw, None, iterations=1)
    if dilate_iteration > 0:
        img_bw = cv2.dilate(img_bw, None, iterations=dilate_iteration)

    # in opencv 3.2, findContours no longer modifies the input image
    # but the code below creates a copy of the image anyway for old
    # version opencv compatibility.
    image, cnts, _ = cv2.findContours(img_bw.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # loop through contours to create rectangles
    rectangles = []
    for c in cnts:
        if cv2.contourArea(c) >= contour_minimal_area:
            x, y, w, h = cv2.boundingRect(c)
            rectangles.append([x, y, w, h])
            cv2.rectangle(img_resized, (x, y), (x+w, y+h), (0, 0, 200), 1)
            #cv2.drawContours(resized, c, -1, (0, 0, 200))

    # merge rectangles
    rectangle_count_before_merge = len(rectangles)
    
    merge_rectangles(rectangles, img_resized)

    rectangle_count_after_merge = len(rectangles)

    # draw merged rectangles for debug purpose
    if not no_gui:
        for r in rectangles:
            x, y, w, h = r
            cv2.rectangle(img_resized, (x, y), (x+w, y+h), (0, 255, 0), 1)

    # process tracers
    if len(tracers) == 0:
        for rect in rectangles:
            tracers.append(Tracer([rect]))
    else:
        new_tracers = []
        for tracer in tracers:
            for t in tracer.process_frame(rectangles):
                if t.missed_frame <= tracer_max_missed_frame:
                    new_tracers.append(t)

        tracers = new_tracers

    # draw debug info
    if not no_gui:
        debug_info = 'frame: %d, tracers: %d, rectangles: %d/%d' % (frame_count, len(tracers), rectangle_count_before_merge, rectangle_count_after_merge)
        cv2.putText(img_resized, debug_info, (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 0, 255))

    show_delay = 100
    # detect motion

    for tracer in tracers:
        if len(tracer.rectangles) <= 1 or tracer.frame_count < tracer_frame_count:
            continue
        
        last = None
        total_distance = 0
        for rect in tracer.rectangles:
            if last is not None:
                x, y = get_rect_center(last)
                x1, y1 = get_rect_center(rect)
                total_distance += math.sqrt((x1-x)*(x1-x) + (y1-y)*(y1-y))
            last = rect

        if total_distance >= tracer_distance:
            if not motion_detected:
                logging.info('first motion detected at frame %d', frame_count)
                show_delay = 10000
            motion_detected = True
            break

    # draw tracers for debug
    if not no_gui:
        for tracer in tracers:
            if len(tracer.rectangles) <= 1:
                continue

            first = tracer.rectangles[0]
            last = tracer.rectangles[-1]
            pt = get_rect_center(first)
            pt1 = get_rect_center(last)
            cv2.line(img_resized, pt, pt1, (0, 255, 0))

    user_pressed_esc = False
    if not no_gui:
        cv2.imshow('frame', img_resized)
        k = cv2.waitKey(show_delay) & 0xff
        user_pressed_esc = k == 27

    if user_pressed_esc or (motion_detected and single_detection):
        break
    last_frame = img_gray

cap.release()
if not no_gui:
    cv2.destroyAllWindows()

if motion_detected:
    exit(2)
else:
    exit(0)
