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
        for name in ['shared/ZSS/Categories.lua', 'shared/ZSS/Core.lua', 'shared/ZSS/Service.lua',
                     'client/ZSS/Window.lua', 'client/ZSS/Client.lua', 'client/ZSS/LootButton.lua']:
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

    def test_discovers_all_loaded_and_dynamic_categories(self):
        self.check('''
            local r = Z.handle(W.player, 'read', readArgs(W))
            local found = {}; for _, id in ipairs(r.categories) do assert(not found[id]); found[id] = true end
            for _, id in ipairs({'FoodP', 'ToolElec', 'WepFire', 'LitS', 'ModdedCategory',
                'CustomOverride', 'Fuel', 'MediaS', 'MediaV'}) do assert(found[id], id) end
            assert(#r.categories == 9)
        ''')

    def test_category_filters_every_matching_type_and_preserves_manual_rules(self):
        self.check('''
            local apple = W.item('Base.Apple', W.inventory)
            local args = mutateArgs(W); args.itemIds = {apple.id}
            Z.handle(W.player, 'add', args)
            args.revision = 1; args.category = 'ToolElec'
            local r = Z.handle(W.player, 'setCategory', args)
            assert(r.code == 'OK' and r.category == 'ToolElec' and r.allowed['Base.Apple'])
            local tool = W.item('Mod.AnyTool'); tool.category = 'ToolElec'
            assert(W.destination:isItemAllowed(tool) and not W.destination:isItemAllowed(apple))
            tool.fullType = 'Other.NewTool'; assert(W.destination:isItemAllowed(tool))
            args.revision = r.revision; args.category = ''
            r = Z.handle(W.player, 'setCategory', args)
            assert(r.code == 'OK' and r.allowed['Base.Apple'])
            assert(W.destination:isItemAllowed(apple) and not W.destination:isItemAllowed(tool))
        ''')

    def test_category_change_requires_empty_container_and_noop_is_safe(self):
        self.check('''
            local args = mutateArgs(W); args.category = 'FoodP'
            local r = Z.handle(W.player, 'setCategory', args)
            W.item('Base.Apple', W.destination)
            args.revision = r.revision
            assert(Z.handle(W.player, 'setCategory', args).code == 'OK')
            args.category = 'WepFire'
            assert(Z.handle(W.player, 'setCategory', args).code == 'CategoryOccupied')
            args.category = ''
            assert(Z.handle(W.player, 'setCategory', args).code == 'CategoryOccupied')
            assert(Z.state(W.destination).category == 'FoodP' and W.object.syncs == 1)
        ''')

    def test_category_rejects_unknown_payloads_and_stale_changes(self):
        self.check('''
            local args = mutateArgs(W)
            for _, value in ipairs({'NotACategory', string.rep('x', 257), true, {}}) do
                args.category = value
                assert(Z.handle(W.player, 'setCategory', args).code == 'UnknownCategory')
            end
            args.category = 'ModdedCategory'
            assert(Z.handle(W.player, 'setCategory', args).code == 'OK')
            args.category = 'Fuel'
            assert(Z.handle(W.player, 'setCategory', args).code == 'Conflict')
        ''')

    def test_category_blocks_manual_edits_and_consumes_drag_without_moving(self):
        self.check('''
            local item = W.item('Base.Apple', W.inventory)
            local args = mutateArgs(W); args.category = 'FoodP'
            local r = Z.handle(W.player, 'setCategory', args)
            args.revision = r.revision; args.itemIds = {item.id}; args.fullType = item.fullType
            assert(Z.handle(W.player, 'add', args).code == 'CategoryMode')
            assert(Z.handle(W.player, 'remove', args).code == 'CategoryMode')
            ISMouseDrag.dragging = {item}
            local window = {identity = 'id', category = 'FoodP', request = function() error('no send') end}
            Z.Window.acceptDrop(window)
            assert(not ISMouseDrag.dragging and window.status == 'IGUI_ZSS_CategoryMode')
            assert(item:getContainer() == W.inventory)
        ''')

    def test_missing_dependency_or_category_fails_closed(self):
        self.check('''
            local args = mutateArgs(W); args.category = 'FoodP'
            Z.handle(W.player, 'setCategory', args)
            local item = W.item('Base.Apple')
            assert(W.destination:isItemAllowed(item))
            getActivatedMods = function() return {contains = function() return false end} end
            assert(Z.handle(W.player, 'read', args).code == 'Dependency')
            assert(not W.destination:isItemAllowed(item))
            getActivatedMods = function() return {contains = function() return true end} end
            Z.state(W.destination).category = 'RemovedCategory'
            assert(not W.destination:isItemAllowed(item))
        ''')

    def test_fluids_media_and_reload_use_current_category(self):
        self.check('''
            local args = mutateArgs(W); args.category = 'Fuel'
            Z.handle(W.player, 'setCategory', args)
            local bottle = W.item('Base.Bottle'); bottle.fluidCategory = 'Fuel'
            assert(W.destination:isItemAllowed(bottle))
            bottle.fluidCategory = 'FoodP'; assert(not W.destination:isItemAllowed(bottle))
            args.revision = 1; args.category = 'MediaS'
            Z.handle(W.player, 'setCategory', args)
            local vhs = W.item('Base.VHS'); vhs.mediaKind = 'Retail-VHS'; vhs.media = true
            assert(W.destination:isItemAllowed(vhs))
            W.destination.accept = nil; Z.onSquareLoaded(W.square)
            assert(W.destination.accept == Z.CALLBACK and W.destination:isItemAllowed(vhs))
        ''')

    def test_category_sort_and_queued_action_recheck(self):
        self.setup_sort()
        self.check('''
            local args = mutateArgs(W); args.category = 'ToolElec'
            Z.handle(W.player, 'setCategory', args)
            local good = W.item('Base.Tool', W.inventory); good.category = 'ToolElec'
            W.item('Base.Apple', W.inventory)
            Z.sortInto(0, W.destination)
            assert(#queuedActions == 1 and queuedActions[1].item == good)
            assert(queuedActions[1]:isValid())
            args.revision = 1; args.category = 'FoodP'; Z.handle(W.player, 'setCategory', args)
            assert(not queuedActions[1]:isValid())
        ''')

    def test_combo_includes_all_categories_and_uses_localized_labels(self):
        self.check('''
            getTextOrNull = function(key) return 'localized:' .. key end
            local combo = {options = {}}
            function combo:clear() self.options = {} end
            function combo:addOptionWithData(text, data) self.options[#self.options+1] = {text=text, data=data} end
            function combo:setSelectedData(data) self.selectedData = data end
            local window = {categoryCombo = combo, category = 'ToolElec'}
            Z.Window.refreshCategories(window, Z.categoryCatalog())
            assert(#combo.options == 10 and combo.selectedData == 'ToolElec')
            local found = {}; for _, option in ipairs(combo.options) do found[option.data] = true end
            assert(found.ToolElec and found.ModdedCategory and found.MediaS and found.Fuel)
            window.category = 'RemovedCategory'
            Z.Window.refreshCategories(window, {})
            assert(#combo.options == 2 and combo.selectedData == 'RemovedCategory')
        ''')

    def test_poll_preserves_unapplied_selection_and_caches_server_category(self):
        self.check('''
            local window = {pending = 1, revision = 2, identity = 'id', container = W.destination,
                refreshList = function(self) self.listRefreshed = true end,
                refreshCategories = function(self) self.comboRefreshed = true end}
            local result = {requestId = 1, revision = 2, identity = 'id', target = {},
                allowed = {}, category = 'FoodP', categories = {'FoodP'}, code = 'OK'}
            Z.Window.receive(window, result)
            assert(not window.comboRefreshed and not window.listRefreshed)
            assert(Z.state(W.destination).category == 'FoodP')
            window.pending = 2; result.requestId = 2; result.identity = 'replacement'
            Z.Window.receive(window, result)
            assert(window.comboRefreshed and window.listRefreshed)
        ''')

    def test_required_mod_metadata(self):
        info = (LUA.parents[1] / 'mod.info').read_text(encoding='utf-8')
        self.assertIn('require=BetterSortCC', info.splitlines())

    def setup_loot_page(self):
        self.check('''
            getSpecificPlayer = function() return W.player end
            P = setmetatable({player = 0, title = 'Shelf', width = 360, font = UIFont.Small,
                inventoryPane = {inventory = W.destination}, children = {},
                addChild = function(self, child) self.children[#self.children + 1] = child end,
                titleBarHeight = function() return 20 end}, {__index = ISInventoryPage})
        ''')

    def test_loot_button_follows_title_and_reuses_existing_control(self):
        self.setup_loot_page()
        self.check('''
            P:prerender()
            local button = P.zssSortButton
            assert(button.visible and button.enabled and #P.children == 1)
            assert(P.drawnX + 6 == button.x and button.x + button.width == 240)
            assert(button.height == 18 and not P.zssCaptureTitle)
            P:prerender(); assert(#P.children == 1)
            P.zssCaptureTitle = true
            assert(Z.lootTitlePosition(P, 'Shelf', 20, 1, false) == 20)
            assert(button.x == 20 + 5 * 6 + 6)
            P.zssCaptureTitle = true
            assert(Z.lootTitlePosition(P, 'Unrelated', 100, 1, true) == 100)
        ''')

    def test_loot_button_hides_on_unsupported_tabs_and_disables_when_inaccessible(self):
        self.setup_loot_page()
        self.check('''
            P:prerender(); local button = P.zssSortButton
            P.inventoryPane.inventory = W.container(nil, 'floor')
            P:prerender(); assert(not button.visible)
            P.inventoryPane.inventory = W.destination
            W.player.dead = true; P:prerender()
            assert(button.visible and not button.enabled)
            local ownPage = {onCharacter = true}
            Z.prepareLootSortButton(ownPage); assert(not ownPage.zssSortButton)
        ''')

    def test_loot_button_resolves_current_tab_at_click_time(self):
        self.setup_loot_page()
        self.check('''
            P:prerender()
            local second = W.container(W.object, 'freezer'); W.object.containers[2] = second
            P.inventoryPane.inventory = second
            local called = 0
            Z.sortInto = function(playerNum, destination)
                called = called + 1; assert(playerNum == 0 and destination == second)
            end
            P.zssSortButton.callback(P.zssSortButton.target)
            assert(called == 1)
            P.inventoryPane.inventory = W.container(nil, 'floor')
            Z.clickLootSort(P); assert(called == 1)
        ''')

    def test_right_click_contains_settings_without_auto_sort(self):
        self.check('''
            local menu = {options = {}, addOption = function(self, text)
                self.options[#self.options + 1] = text
            end}
            Z.onWorldMenu(0, menu, {W.object}, false)
            assert(#menu.options == 1 and menu.options[1] == 'IGUI_ZSS_Settings')
        ''')

    def test_vanilla_fallback_category_without_display_override(self):
        self.check('''
            getScriptManager = function() return {getAllItems = function() return {
                size = function() return 1 end,
                get = function() return {getDisplayCategory = function() end,
                    InstanceItem = function() return {getCategory = function() return 'Item' end} end} end}
            end} end
            local _, known = Z.categoryCatalog(); assert(known.Item)
            local item = W.item('Mod.Plain')
            item.getDisplayCategory = function() end
            item.getCategory = function() return 'Item' end
            assert(Z.itemCategory(item) == 'Item')
            assert(#W.inventory.items == 0 and #W.destination.items == 0)
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
