import asyncio, logging;logging.basicConfig(level=logging.INFO)

import aiomysql

#定义一个log函数，程序执行的时候打印日志，方便查找错误
def log(sql, args=()):
    logging.info('SQL: %s' % sql)

#定义一个全局变量pool，需要连接数据库的时候从pool中获取链接
@asyncio.coroutine
def create_pool(loop, **kw):
    logging.info('create database connection pool...')
    global __pool
    __pool = yield from aiomysql.create_pool(
        host=kw.get('host', 'localhost'),
        port=kw.get('port', 3306),
        user=kw['user'],
        password=kw['password'],
        db=kw['db'],
        charset=kw.get('charset', 'utf8'),
        autocommit=kw.get('autocommit', True),
        maxsize=kw.get('maxsize', 10),
        minsize=kw.get('minsize', 1),
        loop=loop
    )

@asyncio.coroutine
def select(sql, args, size=None):#定义一个select方法，方便操作数据库是重复使用
    log(sql, args)#打印日志
    global __pool#声明pool为全局变量
    with (yield from __pool) as conn:#从连接池获取一个数据库连接
        cur = yield from conn.cursor(aiomysql.DictCursor)#创建一个游标，它与普通游标的不同在于,以dict形式返回结果
        #传入sql语句和实参，把sql语句中的？替换成%s，如果没有实参默认为（）
        yield from cur.execute(sql.replace('?', '%s'), args or ())
        if size:
            rs = yield from cur.fetchmany(size)
        else:
            rs = yield from cur.fetchall()
        yield from cur.close()
        logging.info('rows returned: %s' % len(rs))#len（rs）为结果数
        return rs

@asyncio.coroutine
def execute(sql, args, autocommit=True):
    log(sql)
    with (yield from __pool) as conn:#
        if not autocommit:
            yield from conn.begin()
        try:
            cur = yield from conn.cursor()
            yield from cur.execute(sql.replace('?', '%s'), args)
            affected = cur.rowcount
            yield from cur.close()
            if not autocommit:
                yield from conn.commit()
        except BaseException as e:
            if not autocommit:
                yield from conn.rollback()
            raise
        return affected
#构造占位符，在元类构造insert语句时用到
def create_args_string(num):
    L = []
    for n in range(num):
        L.append('?')
    return ', '.join(L)#list转化为字符串，（，，，，，）

#定义Field父亲类，初始化实例属性
class Field(object):

    def __init__(self, name, column_type, primary_key, default):
        self.name = name #字段名
        self.column_type = column_type #字段类型
        self.primary_key = primary_key #主键
        self.default = default #默认值


    def __str__(self):#调用print方法时指定输出格式为<类名字，字段类型：字段名>,即映射关系
        return '<%s, %s:%s>' % (self.__class__.__name__, self.column_type, self.name)

class StringField(Field):#继承自Field，定义默认值，一般不会用到string类型为主键，所以主键默认为false
    #ddl即数据定义语言
    def __init__(self, name=None, primary_key=False, default=None, ddl='varchar(100)'):
        super().__init__(name, ddl, primary_key, default)

class BooleanField(Field):#布尔字段，主键默认为false

    def __init__(self, name=None, default=False):
        super().__init__(name, 'boolean', False, default)

class IntegerField(Field):#整数

    def __init__(self, name=None, primary_key=False, default=0):
        super().__init__(name, 'bigint', primary_key, default)

class FloatField(Field):#浮点

    def __init__(self, name=None, primary_key=False, default=0.0):
        super().__init__(name, 'real', primary_key, default)

class TextField(Field):

    def __init__(self, name=None, default=None):
        super().__init__(name, 'text', False, default)
#类可以创建一个实例，这是它为什么是一个类的原因。
#但python中一切都是对象，类也不例外，所以类同样也可以被metaclass（元类）所创建
#所以元类实际上可以控制类创建时的行为，就像类可以控制一个实例的生成一样
class ModelMetaclass(type):
	#cls相当于self，即当前创建的类，name为类的名字，bases为类的父类（tuple类型），attrs为类的属性（dict类型），
    def __new__(cls, name, bases, attrs):
        if name=='Model':
            return type.__new__(cls, name, bases, attrs)
        tableName = attrs.get('__table__', None) or name#得到表的名字，默认值为none，没有的话就使用类的名字
        logging.info('found model: %s (table: %s)' % (name, tableName))
        mappings = dict()#映射关系的字典
        fields = []#用来储存User类中除主键外的属性名
        primaryKey = None
        for k, v in attrs.items():#遍历类的属性
            if isinstance(v, Field):
                logging.info('  found mapping: %s ==> %s' % (k, v))
                mappings[k] = v#属性值属于Field类型的话，把他存储进映射表里
                if v.primary_key:#如果该字段的主键值为True，那就找到主键了
                    if primaryKey:#在主键不为空的情况下又找到一个主键就会报错，因为主键有且仅有一个
                        raise StandardError('Duplicate primary key for field: %s' % k)
                    primaryKey = k
                else:
                    fields.append(k)#把所有不是主键的属性名加到field中
        if not primaryKey:#这就表示没有找到主键，也要报错，因为主键一定要有
            raise StandardError('Primary key not found.')
        for k in mappings.keys():
            attrs.pop(k)#将类属性中所有值为Field实例的属性删掉，防止重名冲突
        escaped_fields = list(map(lambda f: '`%s`' % f, fields))#将field转化为sql要求的格式
        attrs['__mappings__'] = mappings # 保存属性和列的映射关系
        attrs['__table__'] = tableName
        attrs['__primary_key__'] = primaryKey # 主键属性名
        attrs['__fields__'] = fields # 除主键外的属性名
        attrs['__select__'] = 'select `%s`, %s from `%s`' % (primaryKey, ', '.join(escaped_fields), tableName)
        attrs['__insert__'] = 'insert into `%s` (%s, `%s`) values (%s)' % (tableName, ', '.join(escaped_fields), primaryKey, create_args_string(len(escaped_fields) + 1))
        attrs['__update__'] = 'update `%s` set %s where `%s`=?' % (tableName, ', '.join(map(lambda f: '`%s`=?' % (mappings.get(f).name or f), fields)), primaryKey)
        attrs['__delete__'] = 'delete from `%s` where `%s`=?' % (tableName, primaryKey)
        return type.__new__(cls, name, bases, attrs)
#orm映射基类，继承自dict，通过metaclass来构造
class Model(dict, metaclass=ModelMetaclass):
#初始化函数，调用父类的方法
    def __init__(self, **kw):
        super(Model, self).__init__(**kw)
#获取实例属性，以user为例子，可以通过user.id来调用属性，也可以通过user[id]来调用
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(r"'Model' object has no attribute '%s'" % key)
#设定实例的属性，可用过user.id=1的方法来设定，更加简便
    def __setattr__(self, key, value):
        self[key] = value
# 通过键取值,若值不存在,返回None
    def getValue(self, key):
        return getattr(self, key, None)
# 通过键取值,若值不存在，就通过field的default（default可callble的话就用callble）来取值
    def getValueOrDefault(self, key):
        value = getattr(self, key, None)
        if value is None:
            field = self.__mappings__[key]
            if field.default is not None:
                value = field.default() if callable(field.default) else field.default
                logging.debug('using default value for %s: %s' % (key, str(value)))
                setattr(self, key, value)# 通过default取到值之后再将其作为当前值
        return value
#定义类方法，关于查询的操作都是通过表执行的，不必创建实例，所以都定义为类方法
    @classmethod
    @asyncio.coroutine
    def findAll(cls, where=None, args=None, **kw):
        sql = [cls.__select__]
        # 我们定义的默认的select语句是通过主键查询的,并不包括where子句
        # 因此若指定有where,需要在select语句中追加关键字
        if where:
            sql.append('where')
            sql.append(where)
        if args is None:
            args = []
        orderBy = kw.get('orderBy', None)#从关键字参数中获取，默认为none
        if orderBy:
            sql.append('order by')
            sql.append(orderBy)
        limit = kw.get('limit', None)#同orderby
        if limit is not None:
            sql.append('limit')
            if isinstance(limit, int):
                sql.append('?')
                args.append(limit)
            elif isinstance(limit, tuple) and len(limit) == 2:
                sql.append('?, ?')
                args.extend(limit)
            else:
                raise ValueError('Invalid limit value: %s' % str(limit))
        rs = yield from select(' '.join(sql), args)
        return [cls(**r) for r in rs]#rs为一个列表，r为字典

    @classmethod
    @asyncio.coroutine
    def findNumber(cls, selectField, where=None, args=None):
        ' find number by select and where. '
        sql = ['select %s _num_ from `%s`' % (selectField, cls.__table__)]
        if where:
            sql.append('where')
            sql.append(where)
        rs = yield from select(' '.join(sql), args, 1)
        if len(rs) == 0:
            return None
        return rs[0]['_num_']

    @classmethod
    @asyncio.coroutine
    def find(cls, pk):
    	# 我们之前已将将数据库的select操作封装在了select函数中,以下select的参数依次就是sql, args, size
        rs = yield from select('%s where `%s`=?' % (cls.__select__, cls.__primary_key__), [pk], 1)
        if len(rs) == 0:
            return None
        return cls(**rs[0])

    @asyncio.coroutine
    def save(self):
        args = list(map(self.getValueOrDefault, self.__fields__))
        args.append(self.getValueOrDefault(self.__primary_key__))
        rows = yield from execute(self.__insert__, args)
        if rows != 1:
            logging.warn('failed to insert record: affected rows: %s' % rows)

    @asyncio.coroutine
    def update(self):
        args = list(map(self.getValue, self.__fields__))
        args.append(self.getValue(self.__primary_key__))
        rows = yield from execute(self.__update__, args)
        if rows != 1:
            logging.warn('failed to update by primary key: affected rows: %s' % rows)

    @asyncio.coroutine
    def remove(self):
        args = [self.getValue(self.__primary_key__)]
        rows = yield from execute(self.__delete__, args)
        if rows != 1:
            logging.warn('failed to remove by primary key: affected rows: %s' % rows)