## example 1
- game/team/player: logs / 2 / 2
- timestamp_ms: 1780031457265 tick: 21
- fsm_state: None
- action: RETREAT target: [46, 46]
- precondition/capi: path_unreachable_or_move_failed / success=False
- obs: score=0 mat=0 hp=300 self={'team_id': 2, 'player_id': 2, 'type': 'Robot', 'state': 'NoneState', 'cell': [46, 45], 'x': 46425, 'y': 45508, 'hp': 150, 'speed': 5000, 'view_range': 0, 'attack': 30, 'attack_range': 1000, 'load': 0, 'capacity': 5, 'goods_total': 0, 'goods': {}}
- prev3: ['GO_ENEMY', 'GO_FACTORY', 'PRESSURE_ENEMY_FACTORY']
- next3: ['GO_ENEMY', 'IDLE', 'RETREAT']

## example 2
- game/team/player: logs / 2 / 2
- timestamp_ms: 1780031458159 tick: 39
- fsm_state: None
- action: RETREAT target: [46, 46]
- precondition/capi: path_unreachable_or_move_failed / success=False
- obs: score=0 mat=0 hp=300 self={'team_id': 2, 'player_id': 2, 'type': 'Robot', 'state': 'NoneState', 'cell': [45, 45], 'x': 45396, 'y': 45508, 'hp': 150, 'speed': 5000, 'view_range': 0, 'attack': 30, 'attack_range': 1000, 'load': 0, 'capacity': 5, 'goods_total': 0, 'goods': {}}
- prev3: ['RETREAT', 'GO_ENEMY', 'IDLE']
- next3: ['GO_CENTER', 'GO_RESOURCE', 'GO_RESOURCE']

## example 3
- game/team/player: logs / 2 / 2
- timestamp_ms: 1780031462909 tick: 134
- fsm_state: None
- action: RETREAT target: [46, 46]
- precondition/capi: path_unreachable_or_move_failed / success=False
- obs: score=0 mat=740 hp=300 self={'team_id': 2, 'player_id': 2, 'type': 'Robot', 'state': 'NoneState', 'cell': [45, 45], 'x': 45188, 'y': 45506, 'hp': 150, 'speed': 5000, 'view_range': 0, 'attack': 30, 'attack_range': 1000, 'load': 0, 'capacity': 5, 'goods_total': 0, 'goods': {}}
- prev3: ['GO_FACTORY', 'GO_FACTORY', 'GO_ENEMY']
- next3: ['GO_RESOURCE', 'GO_FACTORY', 'IDLE']

## example 4
- game/team/player: logs / 2 / 2
- timestamp_ms: 1780031463609 tick: 148
- fsm_state: None
- action: GO_FACTORY target: [46, 46]
- precondition/capi: path_unreachable_or_move_failed / success=False
- obs: score=0 mat=740 hp=300 self={'team_id': 2, 'player_id': 2, 'type': 'Robot', 'state': 'NoneState', 'cell': [45, 45], 'x': 45188, 'y': 45506, 'hp': 150, 'speed': 5000, 'view_range': 0, 'attack': 30, 'attack_range': 1000, 'load': 0, 'capacity': 5, 'goods_total': 0, 'goods': {}}
- prev3: ['GO_ENEMY', 'RETREAT', 'GO_RESOURCE']
- next3: ['IDLE', 'IDLE', 'LOAD_GOODS']

## example 5
- game/team/player: logs / 2 / 2
- timestamp_ms: 1780031467409 tick: 224
- fsm_state: None
- action: GO_FACTORY target: [46, 46]
- precondition/capi: path_unreachable_or_move_failed / success=False
- obs: score=0 mat=735 hp=300 self={'team_id': 2, 'player_id': 2, 'type': 'Robot', 'state': 'NoneState', 'cell': [45, 45], 'x': 45377, 'y': 45506, 'hp': 150, 'speed': 5000, 'view_range': 0, 'attack': 30, 'attack_range': 1000, 'load': 1, 'capacity': 5, 'goods_total': 1, 'goods': {'Semiconductor': 1}}
- prev3: ['GO_CENTER', 'GO_FACTORY', 'IDLE']
- next3: ['RETREAT', 'RETREAT', 'GO_ENEMY']

## example 6
- game/team/player: logs / 2 / 2
- timestamp_ms: 1780031467756 tick: 231
- fsm_state: None
- action: RETREAT target: [46, 46]
- precondition/capi: path_unreachable_or_move_failed / success=False
- obs: score=0 mat=735 hp=300 self={'team_id': 2, 'player_id': 2, 'type': 'Robot', 'state': 'NoneState', 'cell': [45, 45], 'x': 45377, 'y': 45506, 'hp': 150, 'speed': 5000, 'view_range': 0, 'attack': 30, 'attack_range': 1000, 'load': 1, 'capacity': 5, 'goods_total': 1, 'goods': {'Semiconductor': 1}}
- prev3: ['GO_FACTORY', 'IDLE', 'GO_FACTORY']
- next3: ['RETREAT', 'GO_ENEMY', 'GO_FACTORY']

## example 7
- game/team/player: logs / 2 / 2
- timestamp_ms: 1780031468058 tick: 237
- fsm_state: None
- action: RETREAT target: [46, 46]
- precondition/capi: path_unreachable_or_move_failed / success=False
- obs: score=0 mat=735 hp=300 self={'team_id': 2, 'player_id': 2, 'type': 'Robot', 'state': 'NoneState', 'cell': [45, 45], 'x': 45377, 'y': 45506, 'hp': 150, 'speed': 5000, 'view_range': 0, 'attack': 30, 'attack_range': 1000, 'load': 1, 'capacity': 5, 'goods_total': 1, 'goods': {'Semiconductor': 1}}
- prev3: ['IDLE', 'GO_FACTORY', 'RETREAT']
- next3: ['GO_ENEMY', 'GO_FACTORY', 'GO_CENTER']

## example 8
- game/team/player: logs / 2 / 2
- timestamp_ms: 1780031476657 tick: 409
- fsm_state: None
- action: GO_MARKET target: [31, 46]
- precondition/capi: path_unreachable_or_move_failed / success=False
- obs: score=0 mat=1479 hp=300 self={'team_id': 2, 'player_id': 2, 'type': 'Robot', 'state': 'NoneState', 'cell': [32, 45], 'x': 32541, 'y': 45516, 'hp': 150, 'speed': 5000, 'view_range': 0, 'attack': 30, 'attack_range': 1000, 'load': 1, 'capacity': 5, 'goods_total': 1, 'goods': {'Semiconductor': 1}}
- prev3: ['GO_RESOURCE', 'RETREAT', 'GO_RESOURCE']
- next3: ['GO_MARKET', 'PRESSURE_ENEMY_FACTORY', 'GO_MARKET']

## example 9
- game/team/player: logs / 2 / 2
- timestamp_ms: 1780031476958 tick: 415
- fsm_state: None
- action: GO_MARKET target: [31, 46]
- precondition/capi: path_unreachable_or_move_failed / success=False
- obs: score=0 mat=1478 hp=300 self={'team_id': 2, 'player_id': 2, 'type': 'Robot', 'state': 'NoneState', 'cell': [32, 45], 'x': 32541, 'y': 45516, 'hp': 150, 'speed': 5000, 'view_range': 0, 'attack': 30, 'attack_range': 1000, 'load': 1, 'capacity': 5, 'goods_total': 1, 'goods': {'Semiconductor': 1}}
- prev3: ['RETREAT', 'GO_RESOURCE', 'GO_MARKET']
- next3: ['PRESSURE_ENEMY_FACTORY', 'GO_MARKET', 'GO_CENTER']

## example 10
- game/team/player: logs / 2 / 2
- timestamp_ms: 1780031477559 tick: 427
- fsm_state: None
- action: GO_MARKET target: [31, 46]
- precondition/capi: path_unreachable_or_move_failed / success=False
- obs: score=0 mat=1478 hp=300 self={'team_id': 2, 'player_id': 2, 'type': 'Robot', 'state': 'NoneState', 'cell': [31, 45], 'x': 31442, 'y': 45516, 'hp': 150, 'speed': 5000, 'view_range': 0, 'attack': 30, 'attack_range': 1000, 'load': 1, 'capacity': 5, 'goods_total': 1, 'goods': {'Semiconductor': 1}}
- prev3: ['GO_MARKET', 'GO_MARKET', 'PRESSURE_ENEMY_FACTORY']
- next3: ['GO_CENTER', 'GO_FACTORY', 'RETREAT']

## example 11
- game/team/player: logs / 2 / 2
- timestamp_ms: 1780031502258 tick: 921
- fsm_state: None
- action: GO_RESOURCE target: [17, 43]
- precondition/capi: path_unreachable_or_move_failed / success=False
- obs: score=377 mat=1467 hp=300 self={'team_id': 2, 'player_id': 2, 'type': 'Robot', 'state': 'NoneState', 'cell': [17, 42], 'x': 17502, 'y': 42571, 'hp': 150, 'speed': 5200, 'view_range': 0, 'attack': 30, 'attack_range': 1000, 'load': 0, 'capacity': 5, 'goods_total': 0, 'goods': {}}
- prev3: ['PRESSURE_ENEMY_FACTORY', 'PRESSURE_ENEMY_FACTORY', 'GO_FACTORY']
- next3: ['GO_ENEMY', 'RETREAT', 'GO_FACTORY']

## example 12
- game/team/player: logs / 2 / 2
- timestamp_ms: 1780031503460 tick: 945
- fsm_state: None
- action: GO_RESOURCE target: [17, 43]
- precondition/capi: path_unreachable_or_move_failed / success=False
- obs: score=377 mat=1467 hp=300 self={'team_id': 2, 'player_id': 2, 'type': 'Robot', 'state': 'NoneState', 'cell': [18, 42], 'x': 18645, 'y': 42508, 'hp': 150, 'speed': 5200, 'view_range': 0, 'attack': 30, 'attack_range': 1000, 'load': 0, 'capacity': 5, 'goods_total': 0, 'goods': {}}
- prev3: ['GO_ENEMY', 'RETREAT', 'GO_FACTORY']
- next3: ['GO_CENTER', 'GO_RESOURCE', 'GO_ENEMY']

## example 13
- game/team/player: logs / 2 / 2
- timestamp_ms: 1780031505057 tick: 977
- fsm_state: None
- action: GO_RESOURCE target: [17, 43]
- precondition/capi: path_unreachable_or_move_failed / success=False
- obs: score=377 mat=1467 hp=300 self={'team_id': 2, 'player_id': 2, 'type': 'Robot', 'state': 'NoneState', 'cell': [16, 42], 'x': 16276, 'y': 42488, 'hp': 150, 'speed': 5200, 'view_range': 0, 'attack': 30, 'attack_range': 1000, 'load': 0, 'capacity': 5, 'goods_total': 0, 'goods': {}}
- prev3: ['GO_RESOURCE', 'GO_ENEMY', 'GO_ENEMY']
- next3: ['PRESSURE_ENEMY_FACTORY', 'GO_RESOURCE', 'RETREAT']

## example 14
- game/team/player: logs / 2 / 2
- timestamp_ms: 1780031511361 tick: 1103
- fsm_state: None
- action: GO_RESOURCE target: [17, 43]
- precondition/capi: path_unreachable_or_move_failed / success=False
- obs: score=377 mat=1467 hp=300 self={'team_id': 2, 'player_id': 2, 'type': 'Robot', 'state': 'NoneState', 'cell': [18, 43], 'x': 18489, 'y': 43492, 'hp': 150, 'speed': 5200, 'view_range': 0, 'attack': 30, 'attack_range': 1000, 'load': 0, 'capacity': 5, 'goods_total': 0, 'goods': {}}
- prev3: ['RETREAT', 'PRESSURE_ENEMY_FACTORY', 'RETREAT']
- next3: ['GO_CENTER', 'IDLE', 'IDLE']
