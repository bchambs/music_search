from __future__ import absolute_import

import sys
import ast

from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from audiosearch import config as cfg
from audiosearch.redis import client as cache
# from . import tasks


# TODO: refactor redis layout
# Currently resource content is stored as a giant string in cache.
# Redo this so content is stored as native type in cache.
# e.g. artist:similar:Led Zeppelin contains a list of similar artists
def generate_content(resource_id, service_map, trending_track=True, **kwargs):
    new_content = []
    pending_content = []
    result = {}

    page = kwargs.get('page')
    item_count = kwargs.get('item_count')
    resource_id = resource_id.lower().strip()

    cache_data = cache.hgetall(resource_id)
    pipe = cache.pipeline()

    if cache_data:
        # Iterate over map, branch on redis hash status.
        # Build new_content and pending_content where items do not exist or are pending.
        # Result contains paged content or error messages.
        for key, service in service_map.items():
            if key in cache_data:

                content = ast.literal_eval(cache_data[key])

                if content['status'] == "complete":
                    result[key] = page_resource(page, content['data'], item_count)

                elif content['status'] == "pending":
                    pending_content.append(key)

                elif content['status'] == "empty":
                    if 'search' in key:
                        result[key] = {'empty': cfg.EMPTY_MSG}
                    else:
                        result[key] = {'empty': cfg.NO_DATA_MSG}

                elif content['status'] == "failed":
                    result[key] = {'error_message': content['error_message']}

            # New content request.
            else:   
                new_content.append(key)
                pending_content.append(key)

    # Resource does not exist so all keys are new.
    else:   
        new_content = service_map.keys()
        pending_content = new_content

    # Create pending structs in redis to prevent duplicate requests from flooding
    # tasks for a pending item.
    for item in new_content:
        content_struct = {
            'status': "pending",
        }

        tasks.acquire_resource.delay(resource_id, item, service_map[item])
        pipe.hset(resource_id, item, content_struct)

    pipe.expire(resource_id, cfg.REDIS_TTL)
    pipe.execute()

    result['pending_content'] = pending_content

    return result



# Attempt to page a given resource (string, list, dict) by item_count or
# cfg.ITEMS_PER_PAGE
# If resource cannot be paged, return the resource.
def page_resource(page, resource, item_count=None):
    try:
        count = item_count or cfg.ITEMS_PER_PAGE
        paginator = Paginator(resource, count)

        try:
            paged = paginator.page(page)
        except PageNotAnInteger:
            paged = paginator.page(1)
        except EmptyPage:
            paged = paginator.page(paginator.num_pages)
    
        # We must create our own paged context because we cannot seralize Django's paged class.
        result = {
            'data': paged.object_list,
            'next': paged.next_page_number() if paged.has_next() else None,
            'previous': paged.previous_page_number() if paged.has_previous() else None,
            'current': paged.number,
            'total': paged.paginator.num_pages,
            'offset': paged.start_index(),
        }

        return result

    except TypeError:
        return resource




def unescape_html(s):
    if s:
        s = s.replace("&lt;", "<")
        s = s.replace("&gt;", ">")
        s = s.replace("&amp;", "&")
        s = s.replace("&#39;", "'")

    return s




def to_percent(float):
    p = round(float * 100)
    percent = str(p).split('.')

    if len(percent) > 0:
        return percent[0] + " %"
    else:
        return ''




# Used to display (M:S) duration on song profile.
def convert_seconds(t):
    time = str(t)
    minutes = time.split('.')[0]

    if len(minutes) > 1:
        m = int(minutes) / 60
        s = round(t - (m * 60))
        seconds = str(s).split('.')[0]

        if len(seconds) < 2:
            seconds = seconds + "0"

        result['duration'] = "(%s:%s)" %(m, seconds)
    else:
        result['duration'] = "(:%s)" %(minutes[0])



# Attempt to convert item to lowercase, strip white space,
# and remove consecutive spaces.
def normalize(item):
    try:
        normal = item.strip().lower()
        normal = ' '.join(normal.split())
    except AttributeError:
        normal = item

    return normal




# Generate structured reporting message for logging.
# clm = create_logging_message
def clm(description, resource_id=None, content_key=None, service=None):
    line1 = 'ID: "%s"' %(resource_id)
    line2 = 'CONTENT_KEY: "%s"' %(content_key)
    line3 = 'SERVICE: "%s"' %(service)

    msg = "%s\n%s\n%s\n%s" %(description, line1, line2, line3)

    return msg

def t():
    print "hi"
