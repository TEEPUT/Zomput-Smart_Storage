-- Shared rules. No item creation, removal or inventory replacement occurs here.
require "ZSS/Categories"
ZomputSmartStorage = ZomputSmartStorage or {}
local ZSS = ZomputSmartStorage
ZSS.MODULE = "ZomputSmartStorage"
ZSS.KEY = "ZomputSmartStorage_v1"
ZSS.CALLBACK = "ZomputSmartStorage.acceptItem"
ZSS.MAX_RULES = 128
ZSS.MAX_BATCH = 64

function ZSS.isInteger(value, low, high)
    return type(value) == "number" and value == math.floor(value)
        and value >= low and value <= high
end

function ZSS.containerIndex(container)
    if not container then return nil end
    local object = container:getParent()
    if not object or not instanceof(object, "IsoObject")
        or instanceof(object, "IsoGameCharacter") or instanceof(object, "BaseVehicle")
        or instanceof(object, "IsoDeadBody") or instanceof(object, "IsoWorldInventoryObject")
        or not object:getSquare() or object:getObjectIndex() < 0
        or container:getContainingItem() or container:getType() == "floor" then return nil end
    for i = 0, object:getContainerCount() - 1 do
        if object:getContainerByIndex(i) == container then return i end
    end
    return nil
end

function ZSS.state(container)
    local index = ZSS.containerIndex(container)
    if index == nil then return nil end
    local object = container:getParent()
    if not object:hasModData() then return nil end
    local root = object:getModData()[ZSS.KEY]
    if type(root) ~= "table" or root.schema ~= 1 or type(root.containers) ~= "table" then return nil end
    local state = root.containers[tostring(index)]
    if type(state) ~= "table" or type(state.allowed) ~= "table" then return nil end
    return state
end

function ZSS.count(allowed)
    local n = 0
    for _, value in pairs(allowed or {}) do if value == true then n = n + 1 end end
    return n
end

function ZSS.allows(container, item)
    if not item then return false end
    local state = ZSS.state(container)
    if state and state.category and state.category ~= "" then
        local _, known = ZSS.categoryCatalog()
        return known[state.category] == true and ZSS.itemCategory(item) == state.category
    end
    return not state or ZSS.count(state.allowed) == 0 or state.allowed[item:getFullType()] == true
end

local function lookupFunction(name)
    if type(name) ~= "string" or name == "" then return nil end
    local value = _G
    for part in string.gmatch(name, "[^.]+") do
        if type(value) ~= "table" then return nil end
        value = value[part]
    end
    return type(value) == "function" and value or nil
end

-- Engine-level isItemAllowed callback, used by the multiplayer item transaction system.
function ZSS.acceptItem(container, item)
    if not ZSS.allows(container, item) then return false end
    local state = ZSS.state(container)
    if state and state.previousAccept and state.previousAccept ~= ZSS.CALLBACK then
        local previous = lookupFunction(state.previousAccept)
        if not previous then return false end
        return previous(container, item) == true
    end
    return true
end

function ZSS.attach(container)
    local state = ZSS.state(container)
    if not state then return end
    local current = container:getAcceptItemFunction()
    if (state.category and state.category ~= "") or ZSS.count(state.allowed) > 0 then
        if current ~= ZSS.CALLBACK then
            state.previousAccept = current ~= "" and current or nil
            container:setAcceptItemFunction(ZSS.CALLBACK)
        end
    elseif current == ZSS.CALLBACK then
        container:setAcceptItemFunction(state.previousAccept)
    end
end

function ZSS.onObjectAdded(object)
    if not object or not instanceof(object, "IsoObject") or not object:getSquare() then return end
    for i = 0, object:getContainerCount() - 1 do ZSS.attach(object:getContainerByIndex(i)) end
end

function ZSS.onSquareLoaded(square)
    local objects = square:getObjects()
    for i = 0, objects:size() - 1 do ZSS.onObjectAdded(objects:get(i)) end
end

function ZSS.describe(container)
    local index = ZSS.containerIndex(container)
    if index == nil then return nil end
    local object = container:getParent()
    local square = object:getSquare()
    local sprite = object:getSprite()
    return { x = square:getX(), y = square:getY(), z = square:getZ(),
        objectIndex = object:getObjectIndex(), containerIndex = index,
        containerType = container:getType(), sprite = sprite and sprite:getName() or "" }
end

-- Adjacent, on the same floor and on the reachable side of walls/windows.
function ZSS.canAccess(player, container)
    if not player or player:isDead() or ZSS.containerIndex(container) == nil then return false end
    local square = container:getParent():getSquare()
    local current = player:getCurrentSquare()
    if not current or current:getZ() ~= square:getZ() then return false end
    if math.abs(current:getX() - square:getX()) > 1 or math.abs(current:getY() - square:getY()) > 1 then
        return false
    end
    if current ~= square and (current:isBlockedTo(square) or current:isWindowTo(square)) then return false end
    if SafeHouse and SafeHouse.isSafeHouse(square, player:getUsername(), true) then return false end
    return true
end

function ZSS.hasType(container, fullType, depth)
    depth = depth or 0
    -- An unexpectedly deep container tree is treated as occupied, never as empty.
    if depth > 16 then return true end
    local items = container:getItems()
    for i = 0, items:size() - 1 do
        local item = items:get(i)
        if item:getFullType() == fullType then return true end
        if instanceof(item, "InventoryContainer") and ZSS.hasType(item:getInventory(), fullType, depth + 1) then
            return true
        end
    end
    return false
end

function ZSS.isProtected(player, item)
    return item:isFavorite() or item:isEquipped() or player:isEquippedClothing(item)
        or player:getPrimaryHandItem() == item or player:getSecondaryHandItem() == item
end

Events.LoadGridsquare.Add(ZSS.onSquareLoaded)
Events.OnObjectAdded.Add(ZSS.onObjectAdded)
return ZSS
