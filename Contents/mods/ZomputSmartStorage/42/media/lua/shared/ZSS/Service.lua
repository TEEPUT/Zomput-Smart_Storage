require "ZSS/Core"
local ZSS = ZomputSmartStorage

local function resolve(player, args)
    if type(args) ~= "table" or not ZSS.isInteger(args.x, 0, 1000000)
        or not ZSS.isInteger(args.y, 0, 1000000) or not ZSS.isInteger(args.z, -32, 32)
        or not ZSS.isInteger(args.objectIndex, 0, 10000)
        or not ZSS.isInteger(args.containerIndex, 0, 64) then return nil, "Invalid" end
    local current = player and player:getCurrentSquare()
    -- Reject distant requests before loading or inspecting any world square.
    if not current or current:getZ() ~= args.z or math.abs(current:getX() - args.x) > 1
        or math.abs(current:getY() - args.y) > 1 then return nil, "TooFar" end
    local square = getCell():getGridSquare(args.x, args.y, args.z)
    if not square or args.objectIndex >= square:getObjects():size() then return nil, "Gone" end
    local object = square:getObjects():get(args.objectIndex)
    if args.containerIndex >= object:getContainerCount() then return nil, "Gone" end
    local container = object:getContainerByIndex(args.containerIndex)
    local descriptor = ZSS.describe(container)
    if not descriptor or descriptor.containerType ~= args.containerType or descriptor.sprite ~= args.sprite then
        return nil, "Gone"
    end
    if not ZSS.canAccess(player, container) then return nil, "NoAccess" end
    return container
end

local function ensureState(container)
    local data = container:getParent():getModData()
    if data[ZSS.KEY] == nil then data[ZSS.KEY] = {schema = 1, containers = {}} end
    local root = data[ZSS.KEY]
    if type(root) ~= "table" or root.schema ~= 1 or type(root.containers) ~= "table" then return nil end
    local key = tostring(ZSS.containerIndex(container))
    if root.containers[key] == nil then
        root.containers[key] = {identity = tostring(getTimestampMs()) .. ":" .. tostring(ZombRand(1000000000)),
            revision = 0, allowed = {}}
    end
    return ZSS.state(container)
end

local function snapshot(container, args, code)
    local state = ZSS.state(container)
    local result = {requestId = args.requestId, target = ZSS.describe(container), code = code or "OK",
        identity = state.identity, revision = state.revision, allowed = {}}
    for key, value in pairs(state.allowed) do if value == true then result.allowed[key] = true end end
    return result
end

-- Pure command service: multiplayer server and single player use the same validation.
function ZSS.handle(player, command, args)
    if command ~= "read" and command ~= "add" and command ~= "remove" then return nil end
    if type(args) ~= "table" or not ZSS.isInteger(args.requestId, 1, 2147483647) then
        return {code = "Invalid"}
    end
    local container, errorCode = resolve(player, args)
    if not container then return {requestId = args.requestId, code = errorCode} end
    local state = ensureState(container)
    if not state then return {requestId = args.requestId, code = "Invalid"} end
    if command == "read" then
        ZSS.attach(container)
        return snapshot(container, args)
    end
    if args.identity ~= state.identity or args.revision ~= state.revision then
        return snapshot(container, args, "Conflict")
    end
    local changed = false
    if command == "add" then
        if type(args.itemIds) ~= "table" then return snapshot(container, args, "Invalid") end
        local count, additions = 0, {}
        -- Validate the entire batch before committing any of it.
        for key, id in pairs(args.itemIds) do
            count = count + 1
            if count > ZSS.MAX_BATCH or not ZSS.isInteger(key, 1, ZSS.MAX_BATCH)
                or not ZSS.isInteger(id, -2147483648, 2147483647) then
                return snapshot(container, args, "Invalid")
            end
            local item = player:getInventory():getItemWithIDRecursiv(id)
            if not item or not item:getContainer()
                or item:getContainer():getOutermostContainer() ~= player:getInventory() then
                return snapshot(container, args, "NotOwned")
            end
            additions[item:getFullType()] = true
        end
        if count == 0 then return snapshot(container, args, "Invalid") end
        local total = ZSS.count(state.allowed)
        for key in pairs(additions) do if not state.allowed[key] then total = total + 1 end end
        if total > ZSS.MAX_RULES then return snapshot(container, args, "Limit") end
        for key in pairs(additions) do
            if not state.allowed[key] then state.allowed[key] = true; changed = true end
        end
    else
        if type(args.fullType) ~= "string" or #args.fullType > 256 or state.allowed[args.fullType] ~= true then
            return snapshot(container, args, "Invalid")
        end
        if ZSS.hasType(container, args.fullType) then return snapshot(container, args, "Occupied") end
        state.allowed[args.fullType] = nil
        changed = true
    end
    if changed then state.revision = state.revision + 1 end
    ZSS.attach(container)
    if changed then container:getParent():transmitModData() end
    return snapshot(container, args, changed and "OK" or "Duplicate")
end
return ZSS
