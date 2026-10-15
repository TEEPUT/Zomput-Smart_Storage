require "ZSS/Core"
require "ISUI/ISCollapsableWindow"
require "ISUI/ISScrollingListBox"
require "ISUI/ISButton"
require "ISUI/ISMouseDrag"
require "ISUI/ISInventoryPane"

local ZSS = ZomputSmartStorage
ZSS.windows = ZSS.windows or {}
ZSS.nextRequest = 0
ZSS.Window = ISCollapsableWindow:derive("ZSSSettingsWindow")
local Window = ZSS.Window

function ZSS.text(key, ...)
    return getText("IGUI_ZSS_" .. key, ...)
end

function ZSS.notify(player, key, ...)
    if player then HaloTextHelper.addText(player, ZSS.text(key, ...), HaloTextHelper.getColorWhite()) end
end

function Window:new(playerNum, container)
    local textManager = getTextManager()
    local width = math.max(520, textManager:MeasureStringX(UIFont.Small, ZSS.text("Conflict")) + 28,
        textManager:MeasureStringX(UIFont.Small, ZSS.text("DropHint")) + 28,
        textManager:MeasureStringX(UIFont.Small, ZSS.text("Occupied")) + 28)
    width = math.min(width, getPlayerScreenWidth(playerNum) - 24)
    local height = math.max(430, textManager:getFontHeight(UIFont.Small) * 15 + 180)
    height = math.min(height, getPlayerScreenHeight(playerNum) - 24)
    local x = getPlayerScreenLeft(playerNum) + (getPlayerScreenWidth(playerNum) - width) / 2
    local y = getPlayerScreenTop(playerNum) + (getPlayerScreenHeight(playerNum) - height) / 2
    local o = ISCollapsableWindow.new(self, x, y, width, height)
    o.playerNum = playerNum
    o.playerObj = getSpecificPlayer(playerNum)
    o.container = container
    o.target = ZSS.describe(container)
    o.title = ZSS.text("Settings")
    o.resizable = false
    o.status = ZSS.text("Loading")
    o.allowed = {}
    o.lastPoll = 0
    return o
end

local function drawRule(list, y, row, alt)
    if list.selected == row.index then
        list:drawRect(0, y, list.width, list.itemheight, 0.35, 0.25, 0.48, 0.6)
    elseif alt then
        list:drawRect(0, y, list.width, list.itemheight, 0.12, 1, 1, 1)
    end
    list:drawText(row.text, 10, y + 3, 1, 1, 1, 1, UIFont.Small)
    list:drawText(row.item, 10, y + list.fontHeight + 5, 0.65, 0.7, 0.75, 1, UIFont.Small)
    return y + list.itemheight
end

function Window:createChildren()
    ISCollapsableWindow.createChildren(self)
    local fontHeight = getTextManager():getFontHeight(UIFont.Small)
    self.lineHeight = fontHeight + 4
    local top = self:titleBarHeight() + 10 + self.lineHeight * 3
    local bottom = 92
    self.list = ISScrollingListBox:new(12, top, self.width - 24, self.height - top - bottom)
    self.list:initialise()
    self.list.itemheight = math.max(46, fontHeight * 2 + 8)
    self.list.fontHeight = fontHeight
    self.list.doDrawItem = drawRule
    self.list.drawBorder = true
    self.list.onMouseUp = function(list, x, y)
        if ISMouseDrag.dragging then return list.parent:acceptDrop() end
        return true
    end
    self:addChild(self.list)
    self.deleteButton = ISButton:new(12, self.height - 76, 160, 28, ZSS.text("Delete"), self, Window.onDelete)
    self.deleteButton:initialise()
    self:addChild(self.deleteButton)
    self.refreshButton = ISButton:new(182, self.height - 76, 150, 28, ZSS.text("Refresh"), self, Window.onRefresh)
    self.refreshButton:initialise()
    self:addChild(self.refreshButton)
    self.closeButton2 = ISButton:new(self.width - 132, self.height - 76, 120, 28, ZSS.text("Close"), self, Window.close)
    self.closeButton2:initialise()
    self:addChild(self.closeButton2)
end

function Window:refreshList()
    local selected = self.list.items[self.list.selected]
    local selectedType = selected and selected.item
    self.list:clear()
    local rows = {}
    for fullType, allowed in pairs(self.allowed) do
        if allowed == true then
            local script = getScriptManager():FindItem(fullType)
            rows[#rows + 1] = {fullType = fullType, name = script and script:getDisplayName() or fullType}
        end
    end
    table.sort(rows, function(a, b) return a.name < b.name end)
    for _, row in ipairs(rows) do
        self.list:addItem(row.name, row.fullType)
        if row.fullType == selectedType then self.list.selected = #self.list.items end
    end
end

function Window:request(command, extra)
    if self.pending then return false end
    if not ZSS.canAccess(self.playerObj, self.container) then self.status = ZSS.text("NoAccess"); return false end
    local target = ZSS.describe(self.container)
    if not target then self.status = ZSS.text("Gone"); return false end
    ZSS.nextRequest = ZSS.nextRequest % 2147483646 + 1
    local args = {}
    for key, value in pairs(target) do args[key] = value end
    args.requestId = ZSS.nextRequest
    args.identity = self.identity
    args.revision = self.revision
    for key, value in pairs(extra or {}) do args[key] = value end
    self.pending = args.requestId
    self.sentAt = getTimestampMs()
    self.lastPoll = self.sentAt
    if isClient() then
        sendClientCommand(self.playerObj, ZSS.MODULE, command, args)
    else
        require "ZSS/Service"
        self:receive(ZSS.handle(self.playerObj, command, args))
    end
    return true
end

function Window:receive(result)
    if not result or result.requestId ~= self.pending then return end
    self.pending = nil
    if result.target and result.allowed then
        local oldRevision = self.revision
        self.identity = result.identity
        self.revision = result.revision
        self.allowed = result.allowed
        -- The server response is authoritative. This is a local cache, never transmitted by the client.
        local object = self.container:getParent()
        local data = object:getModData()
        local root = data[ZSS.KEY]
        if not root then root = {schema = 1, containers = {}}; data[ZSS.KEY] = root end
        if root.schema == 1 and type(root.containers) == "table" then
            local key = tostring(ZSS.containerIndex(self.container))
            local state = root.containers[key] or {}
            state.identity, state.revision, state.allowed = self.identity, self.revision, self.allowed
            root.containers[key] = state
            ZSS.attach(self.container)
        end
        if oldRevision ~= self.revision then self:refreshList() end
    end
    if result.code ~= "OK" then self.status = ZSS.text(result.code)
    else self.status = ZSS.text("Saved") end
end

function Window:acceptDrop()
    local items = ISInventoryPane.getActualItems(ISMouseDrag.dragging or {})
    local focus = ISMouseDrag.draggingFocus
    -- Consume the drag before any inventory pane can interpret it as a real transfer.
    ISMouseDrag.dragging = nil
    ISMouseDrag.draggingFocus = nil
    if focus then
        focus.dragging = nil
        focus.dragStarted = false
        if focus.draggedItems then focus.draggedItems:reset() end
    end
    if self.pending or not self.identity then self.status = ZSS.text("Wait"); return true end
    local ids, seen = {}, {}
    for _, item in ipairs(items) do
        if not item:getContainer() or item:getContainer():getOutermostContainer() ~= self.playerObj:getInventory() then
            self.status = ZSS.text("NotOwned"); return true
        end
        if not seen[item:getFullType()] then
            if #ids >= ZSS.MAX_BATCH then self.status = ZSS.text("BatchLimit"); return true end
            seen[item:getFullType()] = true
            ids[#ids + 1] = item:getID()
        end
    end
    if #ids > 0 then self:request("add", {itemIds = ids}) end
    return true
end

function Window:onMouseUp(x, y)
    if ISMouseDrag.dragging then return self:acceptDrop() end
    return ISCollapsableWindow.onMouseUp(self, x, y)
end

function Window:onDelete()
    local row = self.list.items[self.list.selected]
    if row and self.identity then self:request("remove", {fullType = row.item}) end
end

function Window:onRefresh()
    self:request("read")
end

function Window:prerender()
    ISCollapsableWindow.prerender(self)
    local top = self:titleBarHeight() + 8
    self:drawText(ZSS.text("DropHint"), 12, top, 0.9, 0.95, 1, 1, UIFont.Small)
    self:drawText(ZSS.text("DataHint"), 12, top + self.lineHeight, 0.65, 0.8, 0.9, 1, UIFont.Small)
    self:drawText(ZSS.text("Rules", ZSS.count(self.allowed), ZSS.MAX_RULES), 12,
        top + self.lineHeight * 2, 0.8, 0.8, 0.8, 1, UIFont.Small)
    self:drawText(self.status or "", 12, self.height - 38, 1, 0.85, 0.55, 1, UIFont.Small)
    local canAccess = ZSS.canAccess(self.playerObj, self.container)
    self.deleteButton:setEnable(canAccess and not self.pending and self.identity ~= nil
        and self.list.items[self.list.selected] ~= nil)
    self.refreshButton:setEnable(canAccess and not self.pending)
    local now = getTimestampMs()
    if self.pending and now - self.sentAt > 10000 then
        self.pending = nil
        self.status = ZSS.text("Timeout")
        self.lastPoll = now
    elseif not self.pending and canAccess and now - self.lastPoll > 2500 then
        self:request("read")
    elseif not canAccess then self.status = ZSS.text("NoAccess") end
end

function Window:close()
    ISCollapsableWindow.close(self)
    self:removeFromUIManager()
    if ZSS.windows[self.playerNum] == self then ZSS.windows[self.playerNum] = nil end
end

function ZSS.openSettings(playerNum, container)
    if not ZSS.canAccess(getSpecificPlayer(playerNum), container) then
        ZSS.notify(getSpecificPlayer(playerNum), "NoAccess"); return
    end
    if ZSS.windows[playerNum] then ZSS.windows[playerNum]:close() end
    local window = Window:new(playerNum, container)
    window:initialise()
    window:addToUIManager()
    ZSS.windows[playerNum] = window
    window:request("read")
end

function ZSS.onServerCommand(module, command, args)
    if module ~= ZSS.MODULE or command ~= "result" then return end
    for _, window in pairs(ZSS.windows) do window:receive(args) end
end
Events.OnServerCommand.Add(ZSS.onServerCommand)
