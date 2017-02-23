# awesome-python-blog 
廖老师的实战过程整个开发下来，感觉难度最大的还是在day3的orm框架以及day5的requesthandler里。
##ORM框架
orm就是对象关系映射，简单的来说就是把关系数据库的一行映射为一个对象，也就是一个类对应一个表，这样，写代码更简单，我们不需要直接写sql语句就可以操控数据库，使用十分方便。编写orm的过程中，主要是要理解metaclass这个黑魔法。元类，顾名思义就是用来创建类并且控制类行为的。当我们定义了一个类的模型，比如用户类的模型。通过编写metaclass就可以在创建类的时候把模型和数据库的映射保存在__mapping__中，后面需要操控sql语句时，就十分方便了。  
##Requesthandler
Requesthandler的主要作用就是为url处理函数分析出需要需要接收的参数，从request中获取必要的参数，调用URL函数，然后把结果转换为web.Response对象。这里借用墨灵的一张图。
![流程图](https://github.com/moling3650/mblog/blob/master/www/app/static/img/Process.png)

整个过程如下：  

1. 客户端（浏览器）发起请求
2. 路由分发请求（这个框架自动帮处理），add_routes函数就是注册路由。
3. 中间件预处理
  - 打印日志
  - 验证用户登陆
  - 收集Request（请求）的数据
4. RequestHandler清理参数并调用控制器（Flask把这些处理请求的控制器称为view functions）
5. 控制器做相关的逻辑判断，有必要时通过ORM框架处理Model的事务。
6. 模型层的主要事务是数据库的查增改删。
7. 控制器再次接管控制权，返回相应的数据。
8. Response_factory根据控制器传过来的数据产生不同的响应。
9. 客户端（浏览器）接收到来自服务器的响应。
