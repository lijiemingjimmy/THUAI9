## example 1
- game/team/player: economy_debug_stage3_short3 / 2 / 0
- timestamp_ms: 1780029884257 tick: 803
- fsm_state: None
- action: UPGRADE_ATTACK target: None
- precondition/capi: ok / success=False
- obs: score=468 mat=1828 hp=300 self={}
- prev3: ['TEAM_IDLE', 'TEAM_IDLE', 'TEAM_IDLE']
- next3: ['UPGRADE_ATTACK', 'TEAM_IDLE', 'TEAM_IDLE']

## example 2
- game/team/player: economy_debug_stage3_short3 / 2 / 0
- timestamp_ms: 1780029884544 tick: 809
- fsm_state: None
- action: UPGRADE_ATTACK target: None
- precondition/capi: ok / success=False
- obs: score=468 mat=1828 hp=300 self={}
- prev3: ['TEAM_IDLE', 'TEAM_IDLE', 'UPGRADE_ATTACK']
- next3: ['TEAM_IDLE', 'TEAM_IDLE', 'UPGRADE_ATTACK']

## example 3
- game/team/player: economy_debug_stage3_short3 / 2 / 0
- timestamp_ms: 1780029885493 tick: 828
- fsm_state: None
- action: UPGRADE_ATTACK target: None
- precondition/capi: ok / success=False
- obs: score=468 mat=1828 hp=300 self={}
- prev3: ['UPGRADE_ATTACK', 'TEAM_IDLE', 'TEAM_IDLE']
- next3: ['UPGRADE_MOVE_SPEED', 'TEAM_IDLE', 'TEAM_IDLE']
