"""대기·이동 결산: 종료 이유, 중단된 대기, 다음 판단, 층 이동 제외. LLM 0콜."""
from movement_summary import MovementSummary

m = MovementSummary()
def tick(t,dec=None,events=None,orders=('wait','wait'),positions=((1,1),(2,1))):
    m.consume('tick',{'turn':t,'decisions':dec or {},'events':events or [],
        'bots':[{'char':str(i+1),'x':p[0],'y':p[1],'alive':True,'order':orders[i]} for i,p in enumerate(positions)]})

tick(1, {'1':{'type':'wait'}}, [{'char':'1','type':'wait','result':'waiting'}])
tick(2)
tick(3, events=[{'char':'1','result':'wait_met'}],orders=(None,'wait'))
tick(4, {'1':{'type':'goto','target':'b2','action_id':'a4'}},
     [{'char':'1','parent_action_id':'a4','resolution':{'type':'goto','phase':'resolved','reason':'arrived'}}],orders=(None,'wait'))
tick(5, {'1':{'type':'goto','target':'b2','action_id':'a5'}},orders=('chase:b2','wait'),positions=((2,2),(3,2)))
s=m.result(); a=s['by_actor']['1']
assert s['multi_wait_ticks']==2
assert a['wait']['ended']=={'wait_met':1} and a['wait']['mean_ticks']==2
assert a['wait']['next_action']=={'goto':1}
assert a['goto_ally']['ended']=={'arrived':1} and a['goto_ally']['next_action']=={'same_ally':1}
assert a['goto_ally']['open'] and a['moving_ticks']==1
m.consume('level',{'turn':5})
tick(6,orders=(None,None),positions=((100,100),(101,100)))
assert m.result()['by_actor']['1']['moving_ticks']==1
tick(7,{'1':{'type':'wait'}},[{'char':'1','type':'wait','result':'waiting'}],orders=('wait',None))
assert m.result()['by_actor']['1']['wait']['open_since']==7
assert m.result()['by_actor']['1']['wait']['completed']==1
tick(22,events=[{'char':'1','result':'wait_bored'}],orders=(None,None))
assert m.result()['by_actor']['1']['wait']['max_ticks']==15
# 새 결정/스냅샷 종료가 명시 종료 이벤트와 중복 집계되지 않는다.
tick(23,{'1':{'type':'wait'}},[{'char':'1','type':'wait','result':'waiting'}],orders=('wait',None))
tick(24,orders=(None,None))
assert m.result()['by_actor']['1']['wait']['ended']=={'wait_met':1,'wait_bored':1,'order_cleared':1}
print('ALL PASS — 대기 종료·미완료·재대기/추적·층 전이·중복 종료 방지')
