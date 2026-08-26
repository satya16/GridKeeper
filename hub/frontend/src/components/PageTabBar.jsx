import { useState } from 'react'
import { Box, Tab, Tabs } from '@mui/material'

// Every page mounts exactly one of these as its own header/tab-bar row --
// carries the sider toggle (mobile only), the page's own tabs, and the
// theme toggle + logout button, via tabBarExtraContent's {left, right}
// slots. Mirrors antd Tabs' tabBarExtraContent, which this replaced (see
// App.css's .page-tabbar rule for the bleed-to-edge/height-64px styling
// that keeps this flush with the sider brand row above it).
export function PageTabBar({ items, tabBarExtraContent }) {
  const [active, setActive] = useState(items[0]?.key)
  const activeItem = items.find((item) => item.key === active) || items[0]

  return (
    <Box>
      <Box className="page-tabbar">
        {tabBarExtraContent?.left}
        <Tabs
          value={activeItem?.key ?? false}
          onChange={(_, key) => setActive(key)}
          sx={{ minHeight: 0, flex: '0 1 auto' }}
        >
          {items.map((item) => (
            <Tab key={item.key} value={item.key} label={item.label} sx={{ minHeight: 64, py: 0 }} />
          ))}
        </Tabs>
        <Box sx={{ ml: 'auto', display: 'flex', alignItems: 'center', gap: 1 }}>{tabBarExtraContent?.right}</Box>
      </Box>
      <Box>{activeItem?.children}</Box>
    </Box>
  )
}
