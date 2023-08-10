"""Search functionality. Can search by name, collection, topics, operations, etc."""

from enum import IntEnum


class SearchCriteria(IntEnum):
    Name = 1
    Topic = 2
    Operation = 3
    Collection = 4
    Output = 5 #TODO
    Language = 6 # TODO
    Accessibility = 7 # TODO
    Cost = 8 # TODO
    License = 9 # TODO
    Credit = 10 # TODO

def is_topic(name: str):
    # TODO: Add ADAM name to topic_ functionality
    return name.startswith("topic_")

def is_operation(name: str):
    # TODO: Add ADAM name to topic_ functionality
    return name.startswith("operation_")

def search(name: str, criteria: SearchCriteria | None, im_feeling_lucky: bool = True):
    # im_feeling_lucky - Return exact match if it is found

    # TODO all that extra search stuff
