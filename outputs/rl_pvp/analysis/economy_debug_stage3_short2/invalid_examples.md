## example 1
- game/team/player: economy_debug_stage3_short2 / 2 / 0
- timestamp_ms: 1780029581839 tick: 14
- fsm_state: None
- action: UPGRADE_ATTACK target: None
- precondition/capi: ok / success=False
- obs: score=0 mat=0 hp=300 self={}
- prev3: ['RECRUIT_ROBOT', 'TEAM_IDLE']
- next3: ['TEAM_IDLE', 'RECRUIT_CAR', 'TEAM_IDLE']

## example 2
- game/team/player: economy_debug_stage3_short2 / 2 / 0
- timestamp_ms: 1780029584472 tick: 67
- fsm_state: None
- action: PRODUCE_SEMICONDUCTOR target: None
- precondition/capi: factory_busy / success=False
- obs: score=0 mat=284 hp=300 self={}
- prev3: ['TEAM_IDLE', 'TEAM_IDLE', 'PRODUCE_TOYS']
- next3: ['TEAM_IDLE', 'PRODUCE_TOYS', 'TEAM_IDLE']

## example 3
- game/team/player: economy_debug_stage3_short2 / 2 / 0
- timestamp_ms: 1780029585072 tick: 79
- fsm_state: None
- action: PRODUCE_TOYS target: None
- precondition/capi: factory_busy / success=False
- obs: score=0 mat=579 hp=300 self={}
- prev3: ['PRODUCE_TOYS', 'PRODUCE_SEMICONDUCTOR', 'TEAM_IDLE']
- next3: ['TEAM_IDLE', 'PRODUCE_TOYS', 'PRODUCE_MEDICINE']

## example 4
- game/team/player: economy_debug_stage3_short2 / 2 / 0
- timestamp_ms: 1780029585672 tick: 91
- fsm_state: None
- action: PRODUCE_TOYS target: None
- precondition/capi: factory_busy / success=False
- obs: score=0 mat=624 hp=300 self={}
- prev3: ['TEAM_IDLE', 'PRODUCE_TOYS', 'TEAM_IDLE']
- next3: ['PRODUCE_MEDICINE', 'PRODUCE_MEDICINE', 'PRODUCE_SEMICONDUCTOR']

## example 5
- game/team/player: economy_debug_stage3_short2 / 2 / 0
- timestamp_ms: 1780029585972 tick: 97
- fsm_state: None
- action: PRODUCE_MEDICINE target: None
- precondition/capi: factory_busy / success=False
- obs: score=0 mat=624 hp=300 self={}
- prev3: ['PRODUCE_TOYS', 'TEAM_IDLE', 'PRODUCE_TOYS']
- next3: ['PRODUCE_MEDICINE', 'PRODUCE_SEMICONDUCTOR', 'PRODUCE_TOYS']

## example 6
- game/team/player: economy_debug_stage3_short2 / 2 / 0
- timestamp_ms: 1780029586572 tick: 109
- fsm_state: None
- action: PRODUCE_SEMICONDUCTOR target: None
- precondition/capi: factory_busy / success=False
- obs: score=0 mat=619 hp=300 self={}
- prev3: ['PRODUCE_TOYS', 'PRODUCE_MEDICINE', 'PRODUCE_MEDICINE']
- next3: ['PRODUCE_TOYS', 'PRODUCE_SEMICONDUCTOR', 'TEAM_IDLE']

## example 7
- game/team/player: economy_debug_stage3_short2 / 2 / 0
- timestamp_ms: 1780029586873 tick: 115
- fsm_state: None
- action: PRODUCE_TOYS target: None
- precondition/capi: factory_busy / success=False
- obs: score=0 mat=619 hp=300 self={}
- prev3: ['PRODUCE_MEDICINE', 'PRODUCE_MEDICINE', 'PRODUCE_SEMICONDUCTOR']
- next3: ['PRODUCE_SEMICONDUCTOR', 'TEAM_IDLE', 'PRODUCE_SEMICONDUCTOR']

## example 8
- game/team/player: economy_debug_stage3_short2 / 2 / 0
- timestamp_ms: 1780029587174 tick: 121
- fsm_state: None
- action: PRODUCE_SEMICONDUCTOR target: None
- precondition/capi: factory_busy / success=False
- obs: score=0 mat=619 hp=300 self={}
- prev3: ['PRODUCE_MEDICINE', 'PRODUCE_SEMICONDUCTOR', 'PRODUCE_TOYS']
- next3: ['TEAM_IDLE', 'PRODUCE_SEMICONDUCTOR', 'TEAM_IDLE']

## example 9
- game/team/player: economy_debug_stage3_short2 / 2 / 0
- timestamp_ms: 1780029587824 tick: 134
- fsm_state: None
- action: PRODUCE_SEMICONDUCTOR target: None
- precondition/capi: factory_busy / success=False
- obs: score=0 mat=619 hp=300 self={}
- prev3: ['PRODUCE_TOYS', 'PRODUCE_SEMICONDUCTOR', 'TEAM_IDLE']
- next3: ['TEAM_IDLE', 'PRODUCE_SEMICONDUCTOR', 'TEAM_IDLE']

## example 10
- game/team/player: economy_debug_stage3_short2 / 2 / 0
- timestamp_ms: 1780029588521 tick: 148
- fsm_state: None
- action: PRODUCE_SEMICONDUCTOR target: None
- precondition/capi: factory_busy / success=False
- obs: score=0 mat=619 hp=300 self={}
- prev3: ['TEAM_IDLE', 'PRODUCE_SEMICONDUCTOR', 'TEAM_IDLE']
- next3: ['TEAM_IDLE', 'TEAM_IDLE', 'PRODUCE_MEDICINE']

## example 11
- game/team/player: economy_debug_stage3_short2 / 2 / 0
- timestamp_ms: 1780029589523 tick: 168
- fsm_state: None
- action: PRODUCE_MEDICINE target: None
- precondition/capi: factory_busy / success=False
- obs: score=0 mat=619 hp=300 self={}
- prev3: ['PRODUCE_SEMICONDUCTOR', 'TEAM_IDLE', 'TEAM_IDLE']
- next3: ['PRODUCE_SEMICONDUCTOR', 'TEAM_IDLE', 'TEAM_IDLE']

## example 12
- game/team/player: economy_debug_stage3_short2 / 2 / 0
- timestamp_ms: 1780029589870 tick: 175
- fsm_state: None
- action: PRODUCE_SEMICONDUCTOR target: None
- precondition/capi: factory_busy / success=False
- obs: score=0 mat=619 hp=300 self={}
- prev3: ['TEAM_IDLE', 'TEAM_IDLE', 'PRODUCE_MEDICINE']
- next3: ['TEAM_IDLE', 'TEAM_IDLE', 'PRODUCE_MEDICINE']

## example 13
- game/team/player: economy_debug_stage3_short2 / 2 / 0
- timestamp_ms: 1780029591120 tick: 200
- fsm_state: None
- action: PRODUCE_SEMICONDUCTOR target: None
- precondition/capi: factory_busy / success=False
- obs: score=0 mat=614 hp=300 self={}
- prev3: ['TEAM_IDLE', 'TEAM_IDLE', 'PRODUCE_MEDICINE']
- next3: ['PRODUCE_SEMICONDUCTOR', 'PRODUCE_MEDICINE', 'PRODUCE_MEDICINE']

## example 14
- game/team/player: economy_debug_stage3_short2 / 2 / 0
- timestamp_ms: 1780029591422 tick: 206
- fsm_state: None
- action: PRODUCE_SEMICONDUCTOR target: None
- precondition/capi: factory_busy / success=False
- obs: score=32 mat=614 hp=300 self={}
- prev3: ['TEAM_IDLE', 'PRODUCE_MEDICINE', 'PRODUCE_SEMICONDUCTOR']
- next3: ['PRODUCE_MEDICINE', 'PRODUCE_MEDICINE', 'PRODUCE_SEMICONDUCTOR']

## example 15
- game/team/player: economy_debug_stage3_short2 / 2 / 0
- timestamp_ms: 1780029591772 tick: 213
- fsm_state: None
- action: PRODUCE_MEDICINE target: None
- precondition/capi: factory_busy / success=False
- obs: score=32 mat=614 hp=300 self={}
- prev3: ['PRODUCE_MEDICINE', 'PRODUCE_SEMICONDUCTOR', 'PRODUCE_SEMICONDUCTOR']
- next3: ['PRODUCE_MEDICINE', 'PRODUCE_SEMICONDUCTOR', 'TEAM_IDLE']

## example 16
- game/team/player: economy_debug_stage3_short2 / 2 / 0
- timestamp_ms: 1780029592124 tick: 220
- fsm_state: None
- action: PRODUCE_MEDICINE target: None
- precondition/capi: factory_busy / success=False
- obs: score=32 mat=614 hp=300 self={}
- prev3: ['PRODUCE_SEMICONDUCTOR', 'PRODUCE_SEMICONDUCTOR', 'PRODUCE_MEDICINE']
- next3: ['PRODUCE_SEMICONDUCTOR', 'TEAM_IDLE', 'TEAM_IDLE']

## example 17
- game/team/player: economy_debug_stage3_short2 / 2 / 0
- timestamp_ms: 1780029592473 tick: 227
- fsm_state: None
- action: PRODUCE_SEMICONDUCTOR target: None
- precondition/capi: factory_busy / success=False
- obs: score=32 mat=614 hp=300 self={}
- prev3: ['PRODUCE_SEMICONDUCTOR', 'PRODUCE_MEDICINE', 'PRODUCE_MEDICINE']
- next3: ['TEAM_IDLE', 'TEAM_IDLE', 'PRODUCE_MEDICINE']

## example 18
- game/team/player: economy_debug_stage3_short2 / 2 / 0
- timestamp_ms: 1780029593471 tick: 247
- fsm_state: None
- action: PRODUCE_MEDICINE target: None
- precondition/capi: factory_busy / success=False
- obs: score=32 mat=614 hp=300 self={}
- prev3: ['PRODUCE_SEMICONDUCTOR', 'TEAM_IDLE', 'TEAM_IDLE']
- next3: ['PRODUCE_TOYS', 'TEAM_IDLE', 'PRODUCE_TOYS']

## example 19
- game/team/player: economy_debug_stage3_short2 / 2 / 0
- timestamp_ms: 1780029593774 tick: 253
- fsm_state: None
- action: PRODUCE_TOYS target: None
- precondition/capi: factory_busy / success=False
- obs: score=32 mat=614 hp=300 self={}
- prev3: ['TEAM_IDLE', 'TEAM_IDLE', 'PRODUCE_MEDICINE']
- next3: ['TEAM_IDLE', 'PRODUCE_TOYS', 'TEAM_IDLE']

## example 20
- game/team/player: economy_debug_stage3_short2 / 2 / 0
- timestamp_ms: 1780029594373 tick: 265
- fsm_state: None
- action: PRODUCE_TOYS target: None
- precondition/capi: factory_busy / success=False
- obs: score=32 mat=829 hp=300 self={}
- prev3: ['PRODUCE_MEDICINE', 'PRODUCE_TOYS', 'TEAM_IDLE']
- next3: ['TEAM_IDLE', 'TEAM_IDLE', 'PRODUCE_SEMICONDUCTOR']
