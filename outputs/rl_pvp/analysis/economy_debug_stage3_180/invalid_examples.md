## example 1
- game/team/player: economy_debug_stage3_180 / 2 / 0
- timestamp_ms: 1780029960766 tick: 603
- fsm_state: None
- action: UPGRADE_ATTACK target: None
- precondition/capi: ok / success=False
- obs: score=468 mat=1372 hp=300 self={}
- prev3: ['TEAM_IDLE', 'TEAM_IDLE', 'TEAM_IDLE']
- next3: ['TEAM_IDLE', 'UPGRADE_ATTACK', 'TEAM_IDLE']

## example 2
- game/team/player: economy_debug_stage3_180 / 2 / 0
- timestamp_ms: 1780029961417 tick: 616
- fsm_state: None
- action: UPGRADE_ATTACK target: None
- precondition/capi: ok / success=False
- obs: score=468 mat=1697 hp=300 self={}
- prev3: ['TEAM_IDLE', 'UPGRADE_ATTACK', 'TEAM_IDLE']
- next3: ['TEAM_IDLE', 'UPGRADE_ATTACK', 'UPGRADE_ATTACK']

## example 3
- game/team/player: economy_debug_stage3_180 / 2 / 0
- timestamp_ms: 1780029962066 tick: 629
- fsm_state: None
- action: UPGRADE_ATTACK target: None
- precondition/capi: ok / success=False
- obs: score=468 mat=1837 hp=300 self={}
- prev3: ['TEAM_IDLE', 'UPGRADE_ATTACK', 'TEAM_IDLE']
- next3: ['UPGRADE_ATTACK', 'UPGRADE_ATTACK', 'UPGRADE_EFFICIENCY']

## example 4
- game/team/player: economy_debug_stage3_180 / 2 / 0
- timestamp_ms: 1780029962416 tick: 636
- fsm_state: None
- action: UPGRADE_ATTACK target: None
- precondition/capi: ok / success=False
- obs: score=468 mat=1837 hp=300 self={}
- prev3: ['UPGRADE_ATTACK', 'TEAM_IDLE', 'UPGRADE_ATTACK']
- next3: ['UPGRADE_ATTACK', 'UPGRADE_EFFICIENCY', 'TEAM_IDLE']

## example 5
- game/team/player: economy_debug_stage3_180 / 2 / 0
- timestamp_ms: 1780029962768 tick: 643
- fsm_state: None
- action: UPGRADE_ATTACK target: None
- precondition/capi: ok / success=False
- obs: score=468 mat=1837 hp=300 self={}
- prev3: ['TEAM_IDLE', 'UPGRADE_ATTACK', 'UPGRADE_ATTACK']
- next3: ['UPGRADE_EFFICIENCY', 'TEAM_IDLE', 'TEAM_IDLE']

## example 6
- game/team/player: economy_debug_stage3_180 / 2 / 0
- timestamp_ms: 1780030041168 tick: 2211
- fsm_state: None
- action: UPGRADE_EFFICIENCY target: None
- precondition/capi: ok / success=False
- obs: score=936 mat=2567 hp=300 self={}
- prev3: ['TEAM_IDLE', 'TEAM_IDLE', 'TEAM_IDLE']
- next3: ['UPGRADE_MOVE_SPEED', 'TEAM_IDLE', 'TEAM_IDLE']

## example 7
- game/team/player: economy_debug_stage3_180 / 2 / 0
- timestamp_ms: 1780030080969 tick: 3007
- fsm_state: None
- action: UPGRADE_EFFICIENCY target: None
- precondition/capi: ok / success=False
- obs: score=936 mat=2567 hp=300 self={}
- prev3: ['TEAM_IDLE', 'TEAM_IDLE', 'TEAM_IDLE']
- next3: ['TEAM_IDLE', 'TEAM_IDLE', 'UPGRADE_EFFICIENCY']

## example 8
- game/team/player: economy_debug_stage3_180 / 2 / 0
- timestamp_ms: 1780030082017 tick: 3028
- fsm_state: None
- action: UPGRADE_EFFICIENCY target: None
- precondition/capi: ok / success=False
- obs: score=936 mat=2567 hp=300 self={}
- prev3: ['UPGRADE_EFFICIENCY', 'TEAM_IDLE', 'TEAM_IDLE']
- next3: ['UPGRADE_EFFICIENCY', 'UPGRADE_ATTACK', 'UPGRADE_ATTACK']

## example 9
- game/team/player: economy_debug_stage3_180 / 2 / 0
- timestamp_ms: 1780030082367 tick: 3035
- fsm_state: None
- action: UPGRADE_EFFICIENCY target: None
- precondition/capi: ok / success=False
- obs: score=936 mat=2567 hp=300 self={}
- prev3: ['TEAM_IDLE', 'TEAM_IDLE', 'UPGRADE_EFFICIENCY']
- next3: ['UPGRADE_ATTACK', 'UPGRADE_ATTACK', 'UPGRADE_EFFICIENCY']

## example 10
- game/team/player: economy_debug_stage3_180 / 2 / 0
- timestamp_ms: 1780030082669 tick: 3041
- fsm_state: None
- action: UPGRADE_ATTACK target: None
- precondition/capi: ok / success=False
- obs: score=936 mat=2567 hp=300 self={}
- prev3: ['TEAM_IDLE', 'UPGRADE_EFFICIENCY', 'UPGRADE_EFFICIENCY']
- next3: ['UPGRADE_ATTACK', 'UPGRADE_EFFICIENCY', 'TEAM_IDLE']

## example 11
- game/team/player: economy_debug_stage3_180 / 2 / 0
- timestamp_ms: 1780030083016 tick: 3048
- fsm_state: None
- action: UPGRADE_ATTACK target: None
- precondition/capi: ok / success=False
- obs: score=936 mat=2567 hp=300 self={}
- prev3: ['UPGRADE_EFFICIENCY', 'UPGRADE_EFFICIENCY', 'UPGRADE_ATTACK']
- next3: ['UPGRADE_EFFICIENCY', 'TEAM_IDLE', 'UPGRADE_ATTACK']

## example 12
- game/team/player: economy_debug_stage3_180 / 2 / 0
- timestamp_ms: 1780030083319 tick: 3054
- fsm_state: None
- action: UPGRADE_EFFICIENCY target: None
- precondition/capi: ok / success=False
- obs: score=936 mat=2567 hp=300 self={}
- prev3: ['UPGRADE_EFFICIENCY', 'UPGRADE_ATTACK', 'UPGRADE_ATTACK']
- next3: ['TEAM_IDLE', 'UPGRADE_ATTACK', 'TEAM_IDLE']

## example 13
- game/team/player: economy_debug_stage3_180 / 2 / 0
- timestamp_ms: 1780030084020 tick: 3068
- fsm_state: None
- action: UPGRADE_ATTACK target: None
- precondition/capi: ok / success=False
- obs: score=936 mat=2567 hp=300 self={}
- prev3: ['UPGRADE_ATTACK', 'UPGRADE_EFFICIENCY', 'TEAM_IDLE']
- next3: ['TEAM_IDLE', 'UPGRADE_MOVE_SPEED', 'UPGRADE_EFFICIENCY']

## example 14
- game/team/player: economy_debug_stage3_180 / 2 / 0
- timestamp_ms: 1780030084717 tick: 3082
- fsm_state: None
- action: UPGRADE_MOVE_SPEED target: None
- precondition/capi: ok / success=False
- obs: score=936 mat=2567 hp=300 self={}
- prev3: ['TEAM_IDLE', 'UPGRADE_ATTACK', 'TEAM_IDLE']
- next3: ['UPGRADE_EFFICIENCY', 'TEAM_IDLE', 'UPGRADE_MOVE_SPEED']

## example 15
- game/team/player: economy_debug_stage3_180 / 2 / 0
- timestamp_ms: 1780030085019 tick: 3088
- fsm_state: None
- action: UPGRADE_EFFICIENCY target: None
- precondition/capi: ok / success=False
- obs: score=936 mat=2567 hp=300 self={}
- prev3: ['UPGRADE_ATTACK', 'TEAM_IDLE', 'UPGRADE_MOVE_SPEED']
- next3: ['TEAM_IDLE', 'UPGRADE_MOVE_SPEED', 'UPGRADE_ATTACK']

## example 16
- game/team/player: economy_debug_stage3_180 / 2 / 0
- timestamp_ms: 1780030085720 tick: 3102
- fsm_state: None
- action: UPGRADE_MOVE_SPEED target: None
- precondition/capi: ok / success=False
- obs: score=936 mat=2567 hp=300 self={}
- prev3: ['UPGRADE_MOVE_SPEED', 'UPGRADE_EFFICIENCY', 'TEAM_IDLE']
- next3: ['UPGRADE_ATTACK', 'UPGRADE_ATTACK', 'UPGRADE_MOVE_SPEED']

## example 17
- game/team/player: economy_debug_stage3_180 / 2 / 0
- timestamp_ms: 1780030086069 tick: 3109
- fsm_state: None
- action: UPGRADE_ATTACK target: None
- precondition/capi: ok / success=False
- obs: score=936 mat=2567 hp=300 self={}
- prev3: ['UPGRADE_EFFICIENCY', 'TEAM_IDLE', 'UPGRADE_MOVE_SPEED']
- next3: ['UPGRADE_ATTACK', 'UPGRADE_MOVE_SPEED', 'TEAM_IDLE']

## example 18
- game/team/player: economy_debug_stage3_180 / 2 / 0
- timestamp_ms: 1780030086416 tick: 3116
- fsm_state: None
- action: UPGRADE_ATTACK target: None
- precondition/capi: ok / success=False
- obs: score=936 mat=2567 hp=300 self={}
- prev3: ['TEAM_IDLE', 'UPGRADE_MOVE_SPEED', 'UPGRADE_ATTACK']
- next3: ['UPGRADE_MOVE_SPEED', 'TEAM_IDLE', 'UPGRADE_MOVE_SPEED']

## example 19
- game/team/player: economy_debug_stage3_180 / 2 / 0
- timestamp_ms: 1780030086719 tick: 3122
- fsm_state: None
- action: UPGRADE_MOVE_SPEED target: None
- precondition/capi: ok / success=False
- obs: score=936 mat=2567 hp=300 self={}
- prev3: ['UPGRADE_MOVE_SPEED', 'UPGRADE_ATTACK', 'UPGRADE_ATTACK']
- next3: ['TEAM_IDLE', 'UPGRADE_MOVE_SPEED', 'TEAM_IDLE']

## example 20
- game/team/player: economy_debug_stage3_180 / 2 / 0
- timestamp_ms: 1780030087416 tick: 3136
- fsm_state: None
- action: UPGRADE_MOVE_SPEED target: None
- precondition/capi: ok / success=False
- obs: score=936 mat=2567 hp=300 self={}
- prev3: ['UPGRADE_ATTACK', 'UPGRADE_MOVE_SPEED', 'TEAM_IDLE']
- next3: ['TEAM_IDLE', 'TEAM_IDLE', 'TEAM_IDLE']
