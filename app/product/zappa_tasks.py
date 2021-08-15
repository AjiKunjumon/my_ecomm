
def pack(_list):
    new_list = list(zip(_list[::2], _list[1::2]))
    if len(_list) % 2:
        new_list.append((_list[-1], None))
    return new_list