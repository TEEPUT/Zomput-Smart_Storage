ZomputSmartStorage = ZomputSmartStorage or {}
local ZSS = ZomputSmartStorage

function ZSS.betterSortingReady()
    return getActivatedMods and getActivatedMods():contains("BetterSortCC")
        and type(BScats) == "table" and type(BSgetCategory) == "function"
end

-- Read the final loaded registry lazily, after Better Sorting's OnGameBoot changes.
-- Other mods' categories are included too; translated labels are never rule IDs.
function ZSS.categoryCatalog()
    if not ZSS.betterSortingReady() then return {}, {} end
    if ZSS.categoryIds then return ZSS.categoryIds, ZSS.categorySet end
    local ids, known = {}, {}
    local function add(id)
        if type(id) == "string" and id ~= "" and #id <= 256 and not known[id] then
            known[id] = true; ids[#ids + 1] = id
        end
    end
    local items = getScriptManager():getAllItems()
    for i = 0, items:size() - 1 do
        local script = items:get(i)
        local category = script:getDisplayCategory()
        if category then add(category)
        else
            -- Vanilla falls back to InventoryItem.getCategory when DisplayCategory
            -- is absent. A temporary unowned instance reveals that category;
            -- it is never added to an inventory or the world.
            local ok, instance = pcall(function() return script:InstanceItem(nil) end)
            if ok and instance then add(instance:getCategory()) end
        end
    end
    for _, definitions in ipairs({BScats, BSoverride or {}, BSfluidCats or {}}) do
        for _, definition in ipairs(definitions) do add(definition.category) end
    end
    -- Better Sorting assigns these to recorded VHS instances, not script items.
    if type(BSupdateMedia) == "function" then add("MediaS"); add("MediaV") end
    table.sort(ids)
    ZSS.categoryIds, ZSS.categorySet = ids, known
    return ids, known
end

function ZSS.itemCategory(item)
    if not item or not ZSS.betterSortingReady() then return nil end
    -- Use Better Sorting's shared resolver on both server and client, so changing
    -- fluid contents cannot leave a stale instance category in the permission check.
    local ok, category = pcall(BSgetCategory, item)
    if not ok then return nil end
    if category then return category end
    local script = item:getScriptItem()
    if script and script:getRecordedMediaCat() == "Retail-VHS" and item:getMediaData() then
        if type(BSupdateMedia) ~= "function" then return nil end
        -- Its Lua helper only needs size/get. Restrict it to this instance rather
        -- than walking an entire inventory during every native accept callback.
        local one = {size = function() return 1 end, get = function() return item end}
        if not pcall(BSupdateMedia, {getAllEvalRecurse = function() return one end}) then return nil end
    end
    return item:getDisplayCategory() or item:getCategory()
end

function ZSS.resetCategoryCatalog()
    ZSS.categoryIds, ZSS.categorySet = nil, nil
end
Events.OnGameStart.Add(ZSS.resetCategoryCatalog)
return ZSS
