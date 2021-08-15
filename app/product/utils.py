import json
from collections import OrderedDict

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


def floating_decimals(f_val, dec):
    prc = "{:."+str(dec)+"f}" #first cast decimal as str
    return prc.format(f_val)


def rating_string(value, lang_code):
    if 1 <= value < 2:
        return "Bad"
    elif 2 <= value < 3:
        return "Good"
    elif 3 <= value < 4:
        return "Very Good"
    elif 4 <= value <= 5:
        return "Excellent"


def json_list(myjson):
    if myjson:
        try:
            json_object = json.loads(json.dumps(myjson))
        except ValueError as e:
            return False, None
        if len(json_object) > 0:
            return True, json_object
        return False, None
    return False, None
