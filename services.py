# -*- coding: utf-8 -*-

from sqlalchemy import *
from sqlalchemy.dialects.postgresql import *
from sqlalchemy.engine.url import URL
from sqlalchemy import event
from sqlalchemy.pool import Pool
from sqlalchemy.orm import mapper, sessionmaker, relationship, clear_mappers
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
import logging
try:
    from services import defaults
except ImportError:
    import defaults

from libs.database import MySQL, PostgreSQL
from libs.domain import Domains
from libs.vhost import Vhosts
from libs.mail import Mailboxes
from libs.user_port import User_ports
from libs.host import Hosts
from libs.subnet import Subnets
from exceptions import DatabaseError, DoesNotExist, PermissionDenied
from sqlalchemy.dialects.postgresql import INET, ARRAY, TEXT

logging.basicConfig()
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)



def on_connect_listener(target, context):
    log = logging.getLogger('services')
    log.debug("Reconnecting to database...")

def on_first_connect_listener(target, context):
    log = logging.getLogger('services')
    log.info("Connecting to database...")

class Services(object):
    """
    Services object

    This object holds most of all methods on services library.

    """
    def __init__(self, username, password, server, port=None, database='services', verbose=False, dynamic_load=True):
        self.__picklethis__ = {}
        self.db = None
        self.dynamic_load = dynamic_load
        self.database = database
        self.database_port = port
        self.db_username = username
        self.db_password = password
        self.server=server
        self.verbose = verbose
        self.defaults = defaults
        self.metadata = None
        self.loaded = False
        if self.verbose:
            logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
        else:
            logging.getLogger('sqlalchemy.engine').setLevel(logging.ERROR)
        self.log = logging.getLogger('services')
        self.customer_id = None
        self.username = self.db_username
        self.session = None
        self.admin_user = False

    def login(self):
        """
        Login to services database

        >> srv = Services(arguments)
        >> srv.login()
        >> 
        """
        self.connect()
        try:
            self.map_objects()
        except Exception as e:
            self.log.exception(e)
        self.getSession()
        if not self.session:
            raise RuntimeError('Invalid login')
        del self.db_password
        if self.username:
            self.customer_id = self.get_user().t_customers_id
        self.load_modules()

    def load_modules(self):
        """
        Load all submodules
        """
        if self.loaded:
            return
        self.mysql = MySQL(self)
        self.postgresql = PostgreSQL(self)
        self.domains = Domains(self)
        self.vhosts = Vhosts(self)
        self.mailboxes = Mailboxes(self)
        self.user_ports = User_ports(self)
        if self.admin_user:
            self.subnets = Subnets(self)
            self.hosts = Hosts(self)
        self.loaded = True

    def commit_session(self):
        """
        Clear session
        """
        self.session.commit()
        self.session = None

    def connect(self, database=None,user=None,password=None,server=None, port=None):
        """
        Connect to database
        """
        if self.db:
            return
        if not database:
            database = self.database
        if not user:
            user = self.db_username
        if not password:
            password = self.db_password
        if not server:
            server = self.server
        if not port:
            port = self.database_port
        if not port:
            port = 5432
        self.db = create_engine(URL('postgresql', username=user, password=password, host=server, port=port, database=database),
                encoding='utf-8', echo=self.verbose, pool_recycle=60)

    def map_objects(self):
        """Function to get session"""
        try:
            if self.metadata or self.loaded:
                # already mapped
                return True
        except:
            # TODO: WAT?
            pass
        try:
            #print("Mapping objects!")
            metadata = MetaData(self.db)
            self.metadata = metadata
            # TODO: this is needed, but why?
            clear_mappers()
            ## map tables to
            event.listen(Pool, 'first_connect', on_first_connect_listener)
            customers = Table('customers', metadata,
                Column("t_customers_id", Integer, primary_key=True),
                Column('name', String, nullable=False),
                Column('aliases', ARRAY(TEXT())))
                #,
                #autoload=True)
            mapper(self.Customers, customers)
        except OperationalError as e:
            self.log.exception(e)
        try:
            domains = Table('domains', self.metadata,
                Column("t_domains_id", Integer, primary_key=True),
                Column("name", String,nullable=False),
                Column('shared', Boolean, nullable=False, default='false'),
                Column("t_customers_id", Integer, ForeignKey('customers.t_customers_id'), nullable=False),
                Column('dns', Boolean, nullable=False),
                Column('refresh_time', Integer, nullable=False, default=text('28800')),
                Column('retry_time', Integer, nullable=False, default=text('7200')),
                Column('expire_time', Integer, nullable=False, default=text('1209600')),
                Column('minimum_cache_time', Integer, nullable=False, default=text('21600')),
                Column('ttl', Integer, nullable=False, default=text('10800')),
                Column('admin_address', String, nullable=True),
                Column('domain_type', Enum('MASTER', 'SLAVE', 'NONE',
                       name="domain_type"), primary_key=False, nullable=False,
                       default=text("'MASTER'::domain_type")),
                Column('masters', ARRAY(TEXT), primary_key=False),
                Column('allow_transfer', ARRAY(TEXT), primary_key=False))
                #autoload=True)
            mapper(self.Domains, domains, properties={
                'customer': relationship(self.Customers, backref='domains'),
            })
        except OperationalError as e:
            self.log.exception(e)
        try:
            users = Table('users', metadata,
                Column("t_users_id", Integer, primary_key=True),
                Column("t_customers_id", Integer, ForeignKey('customers.t_customers_id')),
                Column("t_domains_id", Integer, ForeignKey('domains.t_domains_id')),
                Column('name', String, nullable=False),
                Column('lastname', String, nullable=False),
                Column('firstnames', String, nullable=False),
                Column('phone', String, nullable=False),
                Column('unix_id', Integer, nullable=True),
                Column('admin', Boolean, nullable=True))
                #,autoload=True)
            mapper(self.Users, users, properties={
                'customer': relationship(self.Customers, backref='users'),
                'domain': relationship(self.Domains, backref='users')
                })
        except OperationalError as e:
            self.log.exception(e)
        try:
            services = Table('services', self.metadata,
                            Column("t_services_id", Integer, primary_key=True),
                            Column("server", String),
                            Column("info", String),
                            Column("priority", Integer),
                            Column("service_type", String),
                            Column('ip_address', INET),
                            Column('ipv6_address', INET))
            mapper(self.Services, services)
            return True
        except OperationalError as e:
            self.log.exception(e)


    def getSession(self):
        """
        Get SQLAlchemy database session
        """
        try:
            Session = sessionmaker(bind=self.db)
            self.session = Session()
            self.admin_user = self.is_admin(self.username)
            event.listen(Pool, 'connect', on_connect_listener)
        except OperationalError as e:
            self.log.exception(e)
            raise DatabaseError('Cannot get session')

    def reconnect(self):
        self.session.rollback()

    def safe_commit(self):
        """
        Execute session.commit and report if it success
        Else catch errors, log those and raise proper exception
        """
        try:
            self.session.commit()
        except OperationalError as e:
            # Database connection failed etc
            self.log.exception(e)
            self.session.rollback()
            raise DatabaseError('Cannot commit chantes to database')
        except IntegrityError as e:
            # Wrong values etc passed to function
            self.log.exception(e)
            self.session.rollback()
            return False
        return True

    ###########
    ## Users ##
    ###########

    def require_admin(self):
        """
        Raises PermissionDenied exception if user is not admin
        else returns True

        @Todo: Implement this:
        @self.require_admin
        def function_needing_privileges(self):
        """
        if self.is_admin(self.db_username) is False:
            raise PermissionDenied('Insufficient permissions')
        return True

    def list_users(self):
        """
        List all users
        @TODO: this needs admin privileges?
        """
        users = self.session.query(self.Users)
        try:
            users = users.all()
            self.session.commit()
            return users
        except Exception as e:
            self.log.exception(e)
            self.session.rollback()
            raise RuntimeError('Cannot get users')
        except:
            self.session.rollback()
            raise RuntimeError('Cannot get users')

    def get_customer_id(self):
        """
        Fetch current users customer_id
        @TODO: this should use self.get_current_user method
        """
        user = self.get_user()
        if user:
            return user.t_customers_id

    def get_user(self, username=None):
        """Get current selected user
        Raises DoesNotExist if no user found
        Raises RuntimeError on error

        @TODO: this should be cached
        """
        customer_id = None
        if not username:
            username = self.username
            customer_id = self.customer_id
            if customer_id == None and username == None:
                raise RuntimeError('Select user first')
        user = self.session.query(self.Users)
        if customer_id != None:
            user = user.filter(self.Users.t_customers_id == customer_id)
        if username != None:
            user = user.filter(self.Users.name == username)
        try:
            user = user.one()
            self.session.commit()
            return user
        except NoResultFound:
            raise DoesNotExist('No user %s found' % username)
        except Exception as e:
            self.log.exception(e)
            self.session.rollback()
            raise RuntimeError('Cannot get current user, database error')
        except:
            self.session.rollback()
            raise RuntimeError('Cannot get current user, database error')

    def is_admin(self,username=None):
        """
        Test if user is admin user
        """
        if username is None:
            username = self.db_username
        user =self.get_user(username=username)
        if not user:
            raise DoesNotExist('User %s does not exist in database' % username)
        return user.admin

    def list_aliases(self,user=None):
        """List <username> aliases"""
        alias_list = []
        query = self.session.query(self.Customers.aliases,self.Users.name).join(self.Users, self.Customers.t_customers_id == self.Users.t_customers_id)
        if user is not None:
            query = query.filter(self.Users.name == user)
        elif self.customer_id is not None:
            query = query.filter(self.Users.t_customers_id == self.customer_id)
        else:
            raise RuntimeError('Give either user or customer_id')
        try:
            retvals = query.all()
            if len(retvals) < 1:
                raise RuntimeError('Cannot get alias list')
            for retval in retvals:
                user = retval.name
                alias_list += [alias for alias in retval.aliases if alias is not None]
                alias_list += [user]
            self.session.commit()
            return alias_list
        except NoResultFound:
            if user is not None:
                return DoesNotExist('User %s does not exist' % user)
            else:
                return DoesNotExist('Customer %s does not exist' % self.customer_id)
        except Exception as e:
            self.log.exception(e)
            self.session.rollback()
            raise RuntimeError('Cannot get aliass list')
        except:
            self.session.rollback(e)
            self.log.error('Unknown error while getting aliases list')
            raise RuntimeError('Cannot get aliass list')

    def get_username(self):
        """Get username by t_customers_id"""
        if not self.customer_id:
            raise RuntimeError('Select customer first')
        user = self.get_user()
        if user:
            return user.name
        else:
            raise DoesNotExist('User for customer_id %s does not found' % self.customer_id)

    def add_user(self, username, first_names=None, last_name=None, uid=None):
        """
        TODO: this requires admin privileges!!
        """
        if not self.customer_id:
            raise RuntimeError('Select customer first')
        try:
            user = self.User
            user.name = username
            user.firstname = firstnames
            user.lastname = last_name
            user.unix_id = uid
            user.t_customers_id = self.customer_id
            self.session.add(user)
            self.session.commit()
            self.log.info('Added user %s to customer %s' % (
                                                username, self.customer_id))
        except Exception as e:
            msg = 'Cannot create user %s to customer %s' % (
                                                username, self.customer_id)
            self.log.error(msg)
            self.log.exception(e)
            raise RuntimeError(msg)

    def require_alias(self,alias):
        """Check if there is alias row for <alias>"""
        if self.customer_id is None:
            raise RuntimeError('Select user first')
        aliases = self.list_aliases()
        if alias in aliases:
            return True
        raise RuntimeError('Alias %s not found' % alias)

    def __del__(self):
        try:
            self.session.close()
        except:
            pass

    def __getstate__(self):
        """Used when pickle unloads module"""
        mydict = {'url': self.db.url}
        types = [type(''), type(1), type(None), type(True)]
        for c in self.__dict__:
            if type(self.__dict__[c]) in types:
                mydict[c] = self.__dict__[c]
        return mydict

    def __setstate__(self, d):
        """Used when pickle loads object"""
        self.__dict__.update(d)
        Services.__init__(self, d['url'].username, d['url'].password, d['url'].host,
                port=d['url'].port, database=d['url'].database, verbose=d['verbose'], dynamic_load=d['dynamic_load'])
        self.__dict__.update(d)
        self.login()

    def __getnewargs__(self):
        """Get new object arguments"""
        return ({'username':self.db.url.username, 'password':self.db.url.password, 'server':self.db.url.host,
                'port':self.db.url.port, 'database':self.db.url.database, 'verbose':self.verbose, 'dynamic_load':self.dynamic_load},)


    class Domains(object):
        """Domain object
        object is mapped to the domains view"""


    class Users(object):
        """Users object
        mapped to users view
        self.customer contains Customers object"""


    class Customers(object):
        """Customers object
        mapped to customers view"""


    class Vhosts(object):
        """Vhost object
        object mapped to vhosts view"""


    class Vhost_aliases(object):
        """Vhost alias object
        object is mapped to the vhost_aliases view"""


    class Vhost_redirects(object):
        """Vhost redirect object
        object is mapped to the vhost_redirects view"""

    class Services(object):
        """Vhost servers object
        object is mapped to the services view"""

    class Mailboxes(object):
        """Mailboxes object
        object is mapped to the mailboxes view"""


    class Mail_aliases(object):
        """Mail_aliases object
        object is mapped to the mail_aliases view"""


    class User_port_servers(object):
        """User_port_servers object
        object is mapped to the user_port_server view"""


    class User_ports(object):
        """User_port object
        object is mapped to the user_ports view"""
        pass

    class Databases(object):
        """Databases object
        mapped to databases view"""


    class Database_servers(object):
        """Database_servers object
        mapped to database_servers view"""


    class Subnets(object):
        """Subnets object
        mapped to t_subnets table"""


    class Addresses(object):
        """Mapped to t_addresses table"""


    class Hosts(object):
        """Mapped to t_hosts table"""
