## example 1
- game/team/player: logs / 1 / 3
- timestamp_ms: 1780031612008 tick: 185
- fsm_state: START_HARVEST
- action: HARVEST target: None
- precondition/capi: masked / success=False
- obs: score=143 mat=2195 hp=300 self={'team_id': 1, 'player_id': 3, 'type': 'AutonomousCar', 'state': 'NoneState', 'cell': [7, 27], 'x': 7725, 'y': 27494, 'hp': 100, 'speed': 5000, 'view_range': 0, 'attack': 18, 'attack_range': 1000, 'load': 0, 'capacity': 5, 'goods_total': 0, 'goods': {}}
- prev3: ['GO_RESOURCE', 'GO_RESOURCE', 'IDLE']
- next3: ['HARVEST', 'IDLE', 'GO_RESOURCE']

## example 2
- game/team/player: logs / 1 / 3
- timestamp_ms: 1780031612308 tick: 191
- fsm_state: RECOVER_FROM_FAILURE
- action: HARVEST target: None
- precondition/capi: masked / success=False
- obs: score=143 mat=2195 hp=300 self={'team_id': 1, 'player_id': 3, 'type': 'AutonomousCar', 'state': 'NoneState', 'cell': [7, 27], 'x': 7725, 'y': 27494, 'hp': 100, 'speed': 5000, 'view_range': 0, 'attack': 18, 'attack_range': 1000, 'load': 0, 'capacity': 5, 'goods_total': 0, 'goods': {}}
- prev3: ['GO_RESOURCE', 'IDLE', 'HARVEST']
- next3: ['IDLE', 'GO_RESOURCE', 'GO_RESOURCE']
