-- Small engine boundary mocks; production rule/command/UI code is executed unchanged.
Events = setmetatable({}, {__index = function(t, k)
    local event = {Add = function() end}; rawset(t, k, event); return event
end})
function require() end
function print() end
function instanceof(value, name)
    return value and value.classes and value.classes[name] == true or false
end
function getTimestampMs() return 100000 end
function ZombRand() return 123 end
local function list(items)
    return {size = function() return #items end, get = function(_, i) return items[i + 1] end}
end
function makeWorld()
    local square = {x = 10, y = 20, z = 0, objects = {}}
    function square:getX() return self.x end
    function square:getY() return self.y end
    function square:getZ() return self.z end
    function square:getObjects() return list(self.objects) end
    function square:isBlockedTo() return self.blocked or false end
    function square:isWindowTo() return self.window or false end
    local object = {classes = {IsoObject = true}, data = {}, containers = {}, index = 0, syncs = 0}
    function object:getSquare() return self.square or square end
    function object:getObjectIndex() return self.index end
    function object:getContainerCount() return #self.containers end
    function object:getContainerByIndex(i) return self.containers[i + 1] end
    function object:hasModData() return next(self.data) ~= nil end
    function object:getModData() self.dataReads = (self.dataReads or 0) + 1; return self.data end
    function object:getSprite() return {getName = function() return "test_crate" end} end
    function object:transmitModData() self.syncs = self.syncs + 1 end
    square.objects[1] = object
    local function container(parent, kind)
        local c = {parent = parent, kind = kind, items = {}, capacity = 10, weight = 0}
        function c:getParent() return self.parent end
        function c:getType() return self.kind end
        function c:getContainingItem() return self.containingItem end
        function c:getItems() return list(self.items) end
        function c:getOutermostContainer() return self.outer or self end
        function c:getAcceptItemFunction() return self.accept end
        function c:setAcceptItemFunction(name) self.accept = name end
        function c:getItemWithIDRecursiv(id)
            for _, item in ipairs(self.items) do
                if item.id == id then return item end
                if item.bag then local found = item.bag:getItemWithIDRecursiv(id); if found then return found end end
            end
        end
        function c:isRemoveItemAllowed() return not self.noRemove end
        function c:isItemAllowed(item)
            if self.accept == "ZomputSmartStorage.acceptItem" then return ZomputSmartStorage.acceptItem(self, item) end
            return not self.noAdd
        end
        function c:isInside(item) return self.containingItem == item end
        function c:hasRoomFor(_, item) return self.weight + item.weight <= self.capacity end
        function c:getCapacityWeight() return self.weight end
        function c:getEffectiveCapacity() return self.capacity end
        return c
    end
    local destination = container(object, "crate")
    object.containers[1] = destination
    local inventory = container(nil, "inventory")
    local player = {inventory = inventory, square = square}
    function player:getInventory() return self.inventory end
    function player:isDead() return self.dead or false end
    function player:getCurrentSquare() return self.square end
    function player:getUsername() return "test-player" end
    function player:isEquippedClothing(item) return item.worn or false end
    function player:getPrimaryHandItem() return self.primary end
    function player:getSecondaryHandItem() return self.secondary end
    function player:getPlayerNum() return 0 end
    local nextId = 0
    local function item(fullType, target, weight)
        nextId = nextId + 1
        local i = {id = nextId, fullType = fullType, container = target, weight = weight or 1, classes = {InventoryItem = true}}
        function i:getID() return self.id end
        function i:getFullType() return self.fullType end
        function i:getContainer() return self.container end
        function i:isFavorite() return self.favorite or false end
        function i:isEquipped() return self.equipped or false end
        function i:getIsCraftingConsumed() return self.consumed or false end
        function i:getUnequippedWeight() return self.weight end
        function i:getInventory() return self.bag end
        if target then table.insert(target.items, i) end
        return i
    end
    getCell = function() return {getGridSquare = function(_, x, y, z)
        if x == square.x and y == square.y and z == square.z then return square end
    end} end
    SafeHouse = {isSafeHouse = function() return square.safehouse or false end}
    local world = {square = square, object = object, destination = destination,
        inventory = inventory, player = player, item = item, container = container}
    return world
end

function readArgs(world)
    local args = ZomputSmartStorage.describe(world.destination)
    args.requestId = 1
    return args
end
function mutateArgs(world)
    local args = readArgs(world)
    local response = ZomputSmartStorage.handle(world.player, "read", args)
    args.identity = response.identity
    args.revision = response.revision
    return args
end

ISCollapsableWindow = {derive = function() return {} end}
ISInventoryPane = {getActualItems = function(items) return items end}
ISMouseDrag = {}
getText = function(key, ...) return key end
HaloTextHelper = {addText = function() end, getColorWhite = function() return {} end}
ISInventoryTransferAction = {isValid = function() return true end}
queuedActions = {}
ISTimedActionQueue = {add = function(action) table.insert(queuedActions, action) end}
ISInventoryTransferUtil = {newInventoryTransferAction = function(player, item, src, dest)
    return setmetatable({character = player, item = item, srcContainer = src, destContainer = dest},
        {__index = ISInventoryTransferAction})
end}
