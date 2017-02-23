import orm
import asyncio
import sys
from models import User, Blog, Comment

async def test(loop):
    await orm.create_pool(loop=loop,user='hpf', password='8688680', db='slimshaco')
    y = await User.findAll()
    
    a=y[-1]
    a['admin']=True
    await a.update()
loop = asyncio.get_event_loop()
loop.run_until_complete(test(loop))
loop.run_forever()
