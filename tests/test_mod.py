"""Run with Python + lupa (Lua 5.1). No game data or credentials are required."""
from pathlib import Path
import unittest
import json
import re
from lupa.lua51 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]
LUA = ROOT / 'Contents/mods/ZomputSmartStorage/42/media/lua'


class ModTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute((ROOT / 'tests/harness.lua').read_text(encoding='utf-8'))
        for name in ['shared/ZSS/Core.lua', 'shared/ZSS/Service.lua',
                     'client/ZSS/Window.lua', 'client/ZSS/Client.lua']:
            self.lua.execute((LUA / name).read_text(encoding='utf-8'))
        self.lua.execute('W = makeWorld(); Z = ZomputSmartStorage')

    def check(self, source):
        self.lua.execute(source)

    def test_all_sources_compile_in_lua51(self):
        for path in LUA.rglob('*.lua'):
            with self.subTest(path=path.name):
                self.lua.execute('assert(loadstring(...))', path.read_text(encoding='utf-8'))

    def test_build42_json_translations_have_matching_keys_and_placeholders(self):
        locales = [json.loads((LUA / 'shared/Translate' / language / 'IG_UI.json').read_text(encoding='utf-8'))
                   for language in ('EN', 'KO')]
        self.assertEqual(locales[0].keys(), locales[1].keys())
        for key, english in locales[0].items():
            self.assertEqual(re.findall(r'%[1-4]', english), re.findall(r'%[1-4]', locales[1][key]))
        for path in (LUA / 'client').rglob('*.lua'):
            for key in re.findall(r'ZSS\.text\("(\w+)"', path.read_text(encoding='utf-8')):
                self.assertIn('IGUI_ZSS_' + key, locales[0])

    def test_read_never_moves_items(self):
        self.check('''
            local apple = W.item('Base.Apple', W.inventory)
            local r = Z.handle(W.player, 'read', readArgs(W))
            assert(r.code == 'OK' and r.revision == 0)
            assert(#W.inventory.items == 1 and #W.destination.items == 0)
            assert(W.object.syncs == 0 and apple:getContainer() == W.inventory)
        ''')

    def test_registers_type_metadata_without_transfer(self):
        self.check('''
            local apple = W.item('Base.Apple', W.inventory)
            local args = mutateArgs(W); args.itemIds = {apple.id}
            local r = Z.handle(W.player, 'add', args)
            assert(r.code == 'OK' and r.allowed['Base.Apple'] and r.revision == 1)
            assert(#W.inventory.items == 1 and #W.destination.items == 0 and W.object.syncs == 1)
            assert(W.destination:isItemAllowed(apple))
            assert(not W.destination:isItemAllowed(W.item('Base.Hammer')))
        ''')

    def test_duplicate_does_not_increment_revision(self):
        self.check('''
            local a = W.item('Base.Apple', W.inventory)
            local args = mutateArgs(W); args.itemIds = {a.id, a.id}
            Z.handle(W.player, 'add', args)
            args.revision = 1
            local r = Z.handle(W.player, 'add', args)
            assert(r.code == 'Duplicate' and r.revision == 1 and Z.count(r.allowed) == 1)
        ''')

    def test_rejects_unowned_batch_atomically(self):
        self.check('''
            local a = W.item('Base.Apple', W.inventory)
            local args = mutateArgs(W); args.itemIds = {a.id, 999}
            local r = Z.handle(W.player, 'add', args)
            assert(r.code == 'NotOwned' and Z.count(r.allowed) == 0 and r.revision == 0)
        ''')

    def test_owned_nested_bag_item_can_be_registered(self):
        self.check('''
            local bag = W.item('Base.Bag', W.inventory)
            bag.classes.InventoryContainer = true
            bag.bag = W.container(nil, 'bag'); bag.bag.outer = W.inventory
            local a = W.item('Base.Apple', bag.bag)
            local args = mutateArgs(W); args.itemIds = {a.id}
            assert(Z.handle(W.player, 'add', args).code == 'OK')
            assert(#bag.bag.items == 1)
        ''')

    def test_occupied_type_cannot_be_removed(self):
        self.check('''
            local a = W.item('Base.Apple', W.inventory)
            local args = mutateArgs(W); args.itemIds = {a.id}; Z.handle(W.player, 'add', args)
            W.item('Base.Apple', W.destination)
            args.revision = 1; args.fullType = 'Base.Apple'
            local r = Z.handle(W.player, 'remove', args)
            assert(r.code == 'Occupied' and r.allowed['Base.Apple'] and r.revision == 1)
        ''')

    def test_nested_occupied_type_cannot_be_removed(self):
        self.check('''
            local a = W.item('Base.Apple', W.inventory)
            local args = mutateArgs(W); args.itemIds = {a.id}; Z.handle(W.player, 'add', args)
            local bag = W.item('Base.Bag', W.destination); bag.classes.InventoryContainer = true
            bag.bag = W.container(nil, 'bag'); W.item('Base.Apple', bag.bag)
            args.revision = 1; args.fullType = 'Base.Apple'
            assert(Z.handle(W.player, 'remove', args).code == 'Occupied')
        ''')

    def test_last_removal_restores_previous_filter(self):
        self.check('''
            ExistingMod = {allow = function(c, i) return i.fullType == 'Base.Apple' end}
            W.destination.accept = 'ExistingMod.allow'
            local a = W.item('Base.Apple', W.inventory)
            local args = mutateArgs(W); args.itemIds = {a.id}; Z.handle(W.player, 'add', args)
            assert(Z.acceptItem(W.destination, a))
            args.revision = 1; args.fullType = 'Base.Apple'
            local r = Z.handle(W.player, 'remove', args)
            assert(r.code == 'OK' and Z.count(r.allowed) == 0)
            assert(W.destination.accept == 'ExistingMod.allow')
        ''')

    def test_previous_filter_is_preserved(self):
        self.check('''
            ExistingMod = {allow = function() return false end}
            W.destination.accept = 'ExistingMod.allow'
            local a = W.item('Base.Apple', W.inventory)
            local args = mutateArgs(W); args.itemIds = {a.id}; Z.handle(W.player, 'add', args)
            assert(not Z.acceptItem(W.destination, a))
        ''')

    def test_concurrent_edit_returns_latest_state(self):
        self.check('''
            local a = W.item('Base.Apple', W.inventory)
            local args = mutateArgs(W); args.itemIds = {a.id}; Z.handle(W.player, 'add', args)
            args.fullType = 'Base.Apple'
            local r = Z.handle(W.player, 'remove', args)
            assert(r.code == 'Conflict' and r.revision == 1 and r.allowed['Base.Apple'])
        ''')

    def test_wrong_identity_rejected(self):
        self.check('''
            local args = mutateArgs(W); args.identity = 'stale'; args.itemIds = {1}
            assert(Z.handle(W.player, 'add', args).code == 'Conflict')
        ''')

    def test_distance_floor_wall_window_safehouse_and_death(self):
        for change in ['W.square.x = 30', 'W.square.z = 1', 'W.square.blocked = true',
                       'W.square.window = true', 'W.square.safehouse = true', 'W.player.dead = true']:
            with self.subTest(change=change):
                self.setUp()
                self.check('''
                    local args = readArgs(W)
                    local other = {x = 10, y = 20, z = 0,
                        getX = W.square.getX, getY = W.square.getY, getZ = W.square.getZ,
                        isBlockedTo = function() return W.square.blocked end,
                        isWindowTo = function() return W.square.window end}
                    W.player.square = other
                ''' + change + '''
                    local r = Z.handle(W.player, 'read', args)
                    assert(r.code ~= 'OK')
                ''')

    def test_removed_object_and_changed_container_rejected(self):
        self.check('''
            local args = readArgs(W); W.object.index = -1
            assert(Z.handle(W.player, 'read', args).code == 'Gone')
            W.object.index = 0; W.destination.kind = 'changed'
            assert(Z.handle(W.player, 'read', args).code == 'Gone')
        ''')

    def test_second_container_is_independent(self):
        self.check('''
            local second = W.container(W.object, 'freezer'); W.object.containers[2] = second
            local a = W.item('Base.Apple', W.inventory)
            local args = mutateArgs(W); args.itemIds = {a.id}; Z.handle(W.player, 'add', args)
            assert(not Z.allows(W.destination, W.item('Base.Hammer')))
            assert(Z.allows(second, W.item('Base.Hammer')))
        ''')

    def test_limits_and_invalid_payloads(self):
        self.check('''
            assert(Z.handle(W.player, 'read', nil).code == 'Invalid')
            local args = mutateArgs(W); args.itemIds = {}
            for i = 1, 65 do args.itemIds[i] = W.item('Base.Item' .. i, W.inventory).id end
            assert(Z.handle(W.player, 'add', args).code == 'Invalid')
            args.itemIds = {args.itemIds[1]}
            local state = Z.state(W.destination)
            for i = 1, 128 do state.allowed['Base.Old' .. i] = true end
            assert(Z.handle(W.player, 'add', args).code == 'Limit')
            args.x = 0/0; assert(Z.handle(W.player, 'read', args).code == 'Invalid')
        ''')

    def test_grid_reload_reattaches_filter(self):
        self.check('''
            local a = W.item('Base.Apple', W.inventory)
            local args = mutateArgs(W); args.itemIds = {a.id}; Z.handle(W.player, 'add', args)
            W.destination.accept = nil
            Z.onSquareLoaded(W.square)
            assert(W.destination.accept == Z.CALLBACK)
            assert(not W.destination:isItemAllowed(W.item('Base.Hammer')))
        ''')

    def test_unconfigured_world_load_does_not_allocate_mod_data(self):
        self.check('''
            Z.onSquareLoaded(W.square)
            assert(W.object.dataReads == nil)
            assert(Z.allows(W.destination, W.item('Base.Apple')))
            assert(W.object.dataReads == nil)
        ''')

    def test_drag_consumes_only_metadata(self):
        self.check('''
            local a = W.item('Base.Apple', W.inventory)
            ISMouseDrag.dragging = {a}
            ISMouseDrag.draggingFocus = {dragging = true}
            local window = {playerObj = W.player, identity = 'id', request = function(self, cmd, args)
                assert(cmd == 'add' and args.itemIds[1] == a.id); self.registered = true
            end}
            Z.Window.acceptDrop(window)
            assert(window.registered and not ISMouseDrag.dragging and not ISMouseDrag.draggingFocus)
            assert(a:getContainer() == W.inventory and #W.inventory.items == 1)
        ''')

    def test_drag_from_world_is_rejected(self):
        self.check('''
            ISMouseDrag.dragging = {W.item('Base.Apple', W.destination)}
            local window = {playerObj = W.player, identity = 'id', request = function() error('must not submit') end}
            Z.Window.acceptDrop(window)
            assert(window.status == 'IGUI_ZSS_NotOwned' and not ISMouseDrag.dragging)
        ''')

    def test_drag_during_pending_request_is_consumed_without_registration(self):
        self.check('''
            local a = W.item('Base.Apple', W.inventory)
            ISMouseDrag.dragging = {a}
            local window = {playerObj = W.player, identity = 'id', pending = 7,
                request = function() error('must not submit while pending') end}
            Z.Window.acceptDrop(window)
            assert(window.status == 'IGUI_ZSS_Wait' and not ISMouseDrag.dragging)
            assert(#W.inventory.items == 1 and #W.destination.items == 0)
        ''')

    def test_late_response_is_ignored(self):
        self.check('''
            local window = {pending = 9}
            Z.Window.receive(window, {requestId = 8, code = 'Occupied'})
            assert(window.pending == 9 and window.status == nil)
        ''')

    def test_server_rate_limit_and_unknown_commands(self):
        self.lua.execute((LUA / 'server/ZSS/Server.lua').read_text(encoding='utf-8'))
        self.check('''
            local count, last = 0, nil
            sendServerCommand = function(player, module, command, result)
                count = count + 1; last = result
            end
            Z.onClientCommand(Z.MODULE, 'arbitrary', W.player, {})
            assert(count == 0)
            for i = 1, 13 do
                local args = readArgs(W); args.requestId = i
                Z.onClientCommand(Z.MODULE, 'read', W.player, args)
            end
            assert(count == 13 and last.code == 'Busy' and last.requestId == 13)
        ''')

    def test_manual_transfer_validator_enforces_current_filter(self):
        self.check('''
            local a = W.item('Base.Apple', W.inventory)
            local hammer = W.item('Base.Hammer', W.inventory)
            local args = mutateArgs(W); args.itemIds = {a.id}; Z.handle(W.player, 'add', args)
            local action = ISInventoryTransferUtil.newInventoryTransferAction(W.player, hammer, W.inventory, W.destination)
            assert(not action:isValid())
            action.item = a; assert(action:isValid())
        ''')

    def setup_sort(self):
        self.check('''
            getSpecificPlayer = function() return W.player end
            getPlayerInventory = function() return {inventoryPane = {inventory = W.selected or W.inventory}} end
        ''')

    def test_sort_uses_selected_bag_only(self):
        self.setup_sort()
        self.check('''
            W.item('Base.Apple', W.inventory)
            W.selected = W.container(nil, 'bag'); W.selected.outer = W.inventory
            local selected = W.item('Base.Hammer', W.selected)
            Z.sortInto(0, W.destination)
            assert(#queuedActions == 1 and queuedActions[1].item == selected)
            assert(queuedActions[1].srcContainer == W.selected)
            assert(#W.destination.items == 0)
        ''')

    def test_sort_skips_favorite_equipped_hands_and_consumed(self):
        self.setup_sort()
        self.check('''
            W.item('Base.A', W.inventory).favorite = true
            W.item('Base.B', W.inventory).equipped = true
            W.item('Base.C', W.inventory).worn = true
            W.player.primary = W.item('Base.D', W.inventory)
            W.player.secondary = W.item('Base.E', W.inventory)
            W.item('Base.F', W.inventory).consumed = true
            local good = W.item('Base.G', W.inventory)
            Z.sortInto(0, W.destination)
            assert(#queuedActions == 1 and queuedActions[1].item == good)
        ''')

    def test_sort_capacity_budget_and_filter(self):
        self.setup_sort()
        self.check('''
            local a = W.item('Base.Apple', W.inventory, 4)
            W.item('Base.Apple', W.inventory, 4); W.item('Base.Apple', W.inventory, 4)
            W.item('Base.Hammer', W.inventory, 1)
            local args = mutateArgs(W); args.itemIds = {a.id}; Z.handle(W.player, 'add', args)
            Z.sortInto(0, W.destination)
            assert(#queuedActions == 2)
            assert(queuedActions[1].item.fullType == 'Base.Apple')
        ''')

    def test_queued_sort_revalidates_after_settings_or_favorite_change(self):
        self.setup_sort()
        self.check('''
            local a = W.item('Base.Apple', W.inventory)
            Z.sortInto(0, W.destination)
            local action = queuedActions[1]; assert(action:isValid())
            a.favorite = true; assert(not action:isValid()); a.favorite = false
            local args = mutateArgs(W); args.itemIds = {W.item('Base.Hammer', W.inventory).id}
            Z.handle(W.player, 'add', args)
            assert(not action:isValid())
        ''')


if __name__ == '__main__':
    unittest.main(verbosity=2)
