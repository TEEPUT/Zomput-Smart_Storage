require "ZSS/Window"
require "ISUI/ISInventoryPaneContextMenu"
require "TimedActions/ISTimedActionQueue"
require "TimedActions/ISInventoryTransferUtil"

local ZSS = ZomputSmartStorage

function ZSS.sortInto(playerNum, destination)
    local player = getSpecificPlayer(playerNum)
    local page = getPlayerInventory(playerNum)
    local source = page and page.inventoryPane and page.inventoryPane.inventory
    if not source or source:getOutermostContainer() ~= player:getInventory() then
        ZSS.notify(player, "SelectInventory"); return
    end
    if source == destination or not ZSS.canAccess(player, destination) then
        ZSS.notify(player, "NoAccess"); return
    end
    ZSS.attach(destination)
    local candidates = {}
    local items = source:getItems()
    local skipped = 0
    for i = 0, items:size() - 1 do
        local item = items:get(i)
        if not ZSS.isProtected(player, item) and not item:getIsCraftingConsumed()
            and ZSS.allows(destination, item) and source:isRemoveItemAllowed(item)
            and destination:isItemAllowed(item) and not destination:isInside(item) then
            candidates[#candidates + 1] = item
        else skipped = skipped + 1 end
    end
    table.sort(candidates, function(a, b) return a:getUnequippedWeight() < b:getUnequippedWeight() end)
    local weight = destination:getCapacityWeight()
    local capacity = destination:getEffectiveCapacity(player)
    local queued = 0
    for _, item in ipairs(candidates) do
        local itemWeight = item:getUnequippedWeight()
        if weight + itemWeight <= capacity + 0.0001 and destination:hasRoomFor(player, item) then
            local action = ISInventoryTransferUtil.newInventoryTransferAction(player, item, source, destination)
            if action then
                -- Re-check protected items, source ownership, access and rules when the action runs.
                action.zssAutoSort = true
                ISTimedActionQueue.add(action)
                weight = weight + itemWeight
                queued = queued + 1
            end
        else skipped = skipped + 1 end
    end
    ZSS.notify(player, "Queued", queued, skipped)
end

-- Chain the vanilla validator. All standard drag/drop transfers also consult the current rules.
local vanillaIsValid = ISInventoryTransferAction.isValid
function ISInventoryTransferAction:isValid()
    if self.item and self.destContainer and not ZSS.allows(self.destContainer, self.item) then return false end
    if self.zssAutoSort and (not self.item or ZSS.isProtected(self.character, self.item)
        or not self.srcContainer or self.srcContainer:getOutermostContainer() ~= self.character:getInventory()
        or not ZSS.canAccess(self.character, self.destContainer)) then return false end
    return vanillaIsValid(self)
end

local function addContainerOptions(context, playerNum, container, label)
    local menu = context
    if label then
        local option = context:addOption(label, nil, nil)
        menu = ISContextMenu:getNew(context)
        context:addSubMenu(option, menu)
    end
    menu:addOption(ZSS.text("Settings"), playerNum, ZSS.openSettings, container)
end

function ZSS.onWorldMenu(playerNum, context, worldobjects, test)
    if test then return end
    local seen, containers = {}, {}
    for _, object in ipairs(worldobjects) do
        local square = object:getSquare()
        if square then
            local objects = square:getObjects()
            for i = 0, objects:size() - 1 do
                local candidate = objects:get(i)
                for j = 0, candidate:getContainerCount() - 1 do
                    local container = candidate:getContainerByIndex(j)
                    if not seen[container] and ZSS.containerIndex(container) ~= nil then
                        seen[container] = true
                        containers[#containers + 1] = container
                        ZSS.attach(container)
                    end
                end
            end
        end
    end
    for i, container in ipairs(containers) do
        local label = #containers > 1 and (ZSS.text("Container") .. " " .. i .. " (" .. container:getType() .. ")") or nil
        addContainerOptions(context, playerNum, container, label)
    end
end

function ZSS.onInventoryMenu(playerNum, context, items)
    local loot = getPlayerLoot(playerNum)
    local container = loot and loot.inventoryPane and loot.inventoryPane.inventory
    if container and ZSS.containerIndex(container) ~= nil then
        ZSS.attach(container)
        addContainerOptions(context, playerNum, container, ZSS.text("Container"))
    end
end

Events.OnPreFillWorldObjectContextMenu.Add(ZSS.onWorldMenu)
Events.OnFillInventoryObjectContextMenu.Add(ZSS.onInventoryMenu)
require "ZSS/LootButton"
print("[ZomputSmartStorage] Client UI loaded (1.1.1, Build 42.21).")
