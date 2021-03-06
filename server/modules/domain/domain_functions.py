# encoding: utf-8

"""
Domain logic
"""


from .domain_database import DomainDatabase

from lib.exceptions import AlreadyExist, Invalid, DoesNotExist
from lib.validators import is_positive_numeric
from lib.database.filters import do_limits

from sqlalchemy.orm.exc import NoResultFound


def get_domains(user_id=None, limit=None, offset=None):
    query =  DomainDatabase.query()
    if user_id is not None:
        if is_positive_numeric(user_id) is not True:
            raise Invalid('User id must be positive integer')
        query = query.filter(DomainDatabase.user_id==user_id)
    query = do_limits(query, limit, offset)
    return query.all()


def get_user_domains(user_id, limit=None, offset=None):
    """
    Get user `user_id` domains.
    @param user_id: user user_id
    @type user_id: positive integer
    @param limit: how many entries to return
    @type limit: positive integer
    @param offset: offset in limit
    @type offset: positive integer
    """
    if is_positive_numeric(user_id) is not True:
        raise Invalid('User id must be positive integer')
    return get_domains(user_id=user_id, limit=limit, offset=offset)


def get_domain(name, user_id=None):
    query = DomainDatabase.query()
    if user_id is not None:
        query = query.filter(DomainDatabase.user_id == user_id)
    try:
        return query.filter(DomainDatabase.name == name).one()
    except NoResultFound:
        pass
    raise DoesNotExist("Domain name=%s does not exist" % name)

def get_domain_by_id(domain_id, user_id=None):
    query = DomainDatabase.query()
    if user_id is not None:
        query = query.filter(DomainDatabase.user_id == user_id)
    try:
        return query.filter(DomainDatabase.id == domain_id).one()
    except NoResultFound:
        pass
    raise DoesNotExist("Domain id=%s does not exist" % domain_id)

def add_user_domain(user_id, name, comment=''):
    try:
        get_domain(name)
        raise AlreadyExist('Domain "%s" already exists' % name)
    except DoesNotExist:
        pass
    domain = DomainDatabase()
    domain.user_id = int(user_id)
    domain.name = name
    domain.comment = comment
    domain.save()
    return domain

