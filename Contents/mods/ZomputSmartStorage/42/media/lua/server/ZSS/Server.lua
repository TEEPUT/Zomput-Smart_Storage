require "ZSS/Service"
local ZSS = ZomputSmartStorage
local recent = setmetatable({}, {__mode = "k"})

function ZSS.onClientCommand(module, command, player, args)
    if module ~= ZSS.MODULE or not player then return end
    if command ~= "read" and command ~= "add" and command ~= "remove" and command ~= "setCategory" then return end
    -- Bounded per-player rate limit. State is discarded when the player object is released.
    local now = getTimestampMs()
    local slot = recent[player]
    if not slot or now < slot.start or now - slot.start >= 1000 then
        slot = {start = now, count = 0}; recent[player] = slot
    end
    slot.count = slot.count + 1
    if slot.count > 12 then
        sendServerCommand(player, ZSS.MODULE, "result", {
            requestId = type(args) == "table" and args.requestId or nil, code = "Busy"})
        return
    end
    local ok, result = pcall(ZSS.handle, player, command, args)
    if not ok then
        -- Never print player names, request payloads, world positions or inventory contents.
        print("[ZomputSmartStorage] Command rejected after an internal error.")
        result = {requestId = type(args) == "table" and args.requestId or nil, code = "Internal"}
    end
    if result then sendServerCommand(player, ZSS.MODULE, "result", result) end
end

Events.OnClientCommand.Add(ZSS.onClientCommand)
print("[ZomputSmartStorage] Server rules loaded (1.1.0, Build 42.21).")
