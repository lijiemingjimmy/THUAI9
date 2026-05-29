# THUAI9 PvP CAPI Action Semantics

probe_match_ran: True
source_log_dir: /home/jieming/THUAI9/outputs/rl_pvp/logs/action_semantics_probe

## Harvest
- range: resource nine-grid by cell
- kind: continuous; state HARVESTING; repeated calls while busy fail
- output: team factory source/team.material, not character goodsLoad/currentLoad
- completion: resource depleted, interrupted, leaves range, or thread ends

## ProduceGoods
- range: team process only; no character near factory
- precondition: factory exists, canProduce, enough material/source, storage room, amount>0
- queue: no queue; one production at a time
- output: factory.productInventory
- amount: requested item count; can stop early

## Load
- range: own factory nine-grid
- precondition: idle, amount>0, inventory enough, capacity room
- output: character.goodsLoad/currentLoad

## Sell
- range: market nine-grid
- precondition: idle, amount>0, carried goods enough
- output: score immediately increases; goodsLoad/currentLoad decrease

## Occupy
- range: compute center nine-grid
- precondition: Drone/Robot, idle, center nearby
- kind: continuous; state OCUPPYING; progress while in range

## BuildCharacter
- precondition: team process, canRecruit, enough compute, unused player id, under limit

## UplevelTech
- precondition: team process, enough compute

## Move
- input: angle in world coordinates; target cell uses center world position

## EndAllAction
- effect: interrupts current character action when accepted

## Coordinate Contract
- Character x/y are world coordinates; cell = x//1000, y//1000.
- GetResourceState/GetMarketState/GetFactoryState/GetComputeCenterState use cell coordinates.
- Interaction range is nine-grid in cell space.