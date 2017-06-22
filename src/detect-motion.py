import numpy as np
import cv2
import sys
import time
import math
from collections import deque

class Tracer():
    def __init__(self, rect_list, frame_count = 1, missed_frame = 0):
        self.rectangles = []
        self.rectangles.extend(rect_list)
        self.frame_count = frame_count
        self.missed_frame = missed_frame

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
            if area_variation > 1.1:
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

def merge_rectangles(rectangles):
    g = 0
    while len(rectangles) > 1 and g < len(rectangles):
        merge_list = []
        x, y, w, h = rectangles[g]
        for idx in xrange(g+1, len(rectangles) - 1):
            if has_intersection(rectangles[g], rectangles[idx]):
                merge_list.append(idx)
                x, y, w, h = merge_rect((x, y, w, h), rectangles[idx])
        if len(merge_list) > 0:
            rectangles[g] = (x, y, w, h)
            for idx in reversed(merge_list):
                del rectangles[idx]
        else:
            g += 1

# no motion
#cap = cv2.VideoCapture('../sample-videos/20170615T102512.mp4')

# with motion
cap = cv2.VideoCapture('../sample-videos/20170608T202125.mp4')

# night, car moving out
#cap = cv2.VideoCapture('../sample-videos/00.06.26-00.06.54.mp4')

#cap = cv2.VideoCapture('../sample-videos/20170615T103505 cloud butterfly.mp4')
#cap = cv2.VideoCapture('../sample-videos/21.18.00-21.18.38 car light on garage.mp4')
#cap = cv2.VideoCapture('../sample-videos/12.06.20-12.06.48 front cloud.mp4')
#cap = cv2.VideoCapture('../sample-videos/21.48.00-21.50.00 insects.mp4')
#cap = cv2.VideoCapture('../sample-videos/22.12.00-22.14.00 faraway move and insects.mp4')

# fgbg = cv2.createBackgroundSubtractorMOG()
#fgbg = cv2.createBackgroundSubtractorKNN()
#fgbg = cv2.createBackgroundSubtractorMOG2()

#kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(3,3))
#fgbg = cv2.createBackgroundSubtractorGMG()

last_frame = None
queue = deque()
tracers = []
#font = cv2.InitFont(cv.CV_FONT_HERSHEY_SIMPLEX, 1, 1, 0, 3, 8)

while(1):
    ret, frame = cap.read()

    if not ret:
        break

    #frame = cv2.GaussianBlur(frame, (5, 5), 0)
    resized = cv2.resize(frame, (0,0), fx=0.5, fy=0.5)
    img = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    

    if last_frame is None:
        last_frame = img
        continue

    delta = cv2.absdiff(last_frame, img)
    thresh = cv2.threshold(delta, 50, 255, cv2.THRESH_BINARY)[1]
    #fgmask = fgbg.apply(img)
    #fgmask = cv2.morphologyEx(fgmask, cv2.MORPH_OPEN, kernel)

    #thresh = cv2.erode(thresh, None, iterations=1)
    thresh = cv2.dilate(thresh, None, iterations=2)
    # in opencv 3.2, findContours no longer modifies the input image
    # but the code below creates a copy of the image anyway for old
    # version opencv compatibility.
    image, cnts, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    #contour_list = []
    rectangles = []
    for c in cnts:
        if cv2.contourArea(c) > 15:
            #contour_list.append(c)
            x, y, w, h = cv2.boundingRect(c)
            rectangles.append([x, y, w, h])
            #cv2.rectangle(resized, (x, y), (x+w, y+h), (0, 255, 0), 1)
            #cv2.drawContours(resized, c, -1, (0, 0, 200))
            #frame_pause = 100
    
    # merge rectangles
    rectangle_count_before_merge = len(rectangles)
    
    merge_rectangles(rectangles)

    rectangle_count_after_merge = len(rectangles)

    for r in rectangles:
        x, y , w, h = r
        cv2.rectangle(resized, (x, y), (x+w, y+h), (0, 0, 255), 1)

    if len(tracers) == 0:
        for rect in rectangles:
            tracers.append(Tracer([rect]))
    else:
        new_tracers = []
        for tracer in tracers:
            for t in tracer.process_frame(rectangles):
                if t.missed_frame < 5:
                    new_tracers.append(t)

        tracers = new_tracers

    #queue.append(contour_list)
    # if len(queue) > 10:
    #     for contour_list in queue:
    #         for c in contour_list:
    #             x, y, w, h = cv2.boundingRect(c)
    #             cv2.rectangle(resized, (x, y), (x+w, y+h), (0, 255, 0), 1)
    #     queue.popleft()
    #print('tracer size: %d'%(len(tracers)))
    debug_info = 'tracer count: %d, rect count before: %d, rect count after: %d' % (len(tracers), rectangle_count_before_merge, rectangle_count_after_merge)
    cv2.putText(resized, debug_info, (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 0, 255))
    for tracer in tracers:
        if len(tracer.rectangles) == 1:
            continue
        # calculate color
        #color = (tracer.frame_count - tracer.missed_frame) * 255 / tracer.frame_count
        
        last = None
        for rect in tracer.rectangles:
            if last is not None:
                x, y, w, h = last
                x1, y1, w1, h1 = rect
                pt = (x + w / 2, y + h / 2)
                pt1 = (x1 + w1 / 2, y1 + h1 / 2)
                cv2.line(resized, pt, pt1, (0, 0, 255))
            last = rect

    cv2.imshow('frame', resized)
    k = cv2.waitKey(50) & 0xff
    if k == 27:     # ESC: 27
        break

    last_frame = img

cap.release()
cv2.destroyAllWindows()
