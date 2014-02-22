# encoding: utf-8

from lib.input import UserIDValidator, DomainValidator, InputParser, \
    IntegerValidator, StringValidator


class PortGetValidator(InputParser):
    user_id = UserIDValidator('user_id')
    limit = IntegerValidator('limit', positive=True, required=False)
    offset = IntegerValidator('offset', positive=True, required=False)

