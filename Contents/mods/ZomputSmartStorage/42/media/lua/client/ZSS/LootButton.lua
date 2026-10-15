require "ZSS/Core"
require "ISUI/ISInventoryPage"
require "ISUI/ISButton"
local ZSS = ZomputSmartStorage

function ZSS.clickLootSort(page)
    -- Resolve the selected container at click time, never a previous shelf tab.
    local container = page.inventoryPane and page.inventoryPane.inventory
    if not page.onCharacter and ZSS.containerIndex(container) ~= nil then
        ZSS.sortInto(page.player, container)
    end
end

function ZSS.prepareLootSortButton(page)
    if page.onCharacter then return end
    local container = page.inventoryPane and page.inventoryPane.inventory
    local supported = ZSS.containerIndex(container) ~= nil
    if supported and not page.zssSortButton then
        local button = ISButton:new(0, 1, 1, 1, ZSS.text("Sort"), page, ZSS.clickLootSort)
        button:initialise()
        page:addChild(button)
        page.zssSortButton = button
    end
    local button = page.zssSortButton
    if not button then return end
    button:setVisible(false)
    if supported then
        button:setWidth(getTextManager():MeasureStringX(UIFont.Small, ZSS.text("Sort")) + 12)
        button:setHeight(page:titleBarHeight() - 2)
        button:setEnable(ZSS.canAccess(getSpecificPlayer(page.player), container))
        page.zssCaptureTitle = true
    end
end

-- Follow the actual title drawing position instead of assuming a fixed title
-- width. This also follows container renames, font changes and window resizing.
function ZSS.lootTitlePosition(page, text, x, y, rightAligned)
    local button = page.zssSortButton
    local title = page.title
    if not page.zssCaptureTitle or not button or not title or type(text) ~= "string"
        or (text ~= title and string.sub(text, 1, #title + 2) ~= title .. ": ")
        or y < 0 or y >= page:titleBarHeight() then return x end
    local buttonX
    if rightAligned then
        buttonX = x - button.width
        x = buttonX - 6
    else
        buttonX = x + getTextManager():MeasureStringX(page.font or UIFont.Small, text) + 6
    end
    button:setX(buttonX)
    button:setY(1)
    button:setVisible(true)
    page.zssCaptureTitle = false
    return x
end

local drawText = ISInventoryPage.drawText
function ISInventoryPage:drawText(text, x, y, ...)
    return drawText(self, text, ZSS.lootTitlePosition(self, text, x, y, false), y, ...)
end
local drawTextRight = ISInventoryPage.drawTextRight
function ISInventoryPage:drawTextRight(text, x, y, ...)
    return drawTextRight(self, text, ZSS.lootTitlePosition(self, text, x, y, true), y, ...)
end
local prerender = ISInventoryPage.prerender
function ISInventoryPage:prerender()
    self.zssCaptureTitle = false
    ZSS.prepareLootSortButton(self)
    prerender(self)
    self.zssCaptureTitle = false
end
