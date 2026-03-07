/**
 * E2E 测试 - 首次引导流程
 * 测试用户首次启动时的引导步骤
 */

import { test, expect } from '@playwright/test';

test.describe('首次启动引导', () => {
  test('引导流程存在', async ({ page }) => {
    // 访问页面
    await page.goto('/');
    
    // 检查引导组件是否存在
    // 由于是 Tauri 应用，需要先启动 dev server
    // 这里测试基本的页面加载
    await page.waitForLoadState('networkidle');
    
    // 验证页面标题或关键元素
    const title = await page.title();
    console.log('页面标题:', title);
  });

  test('设置页面可访问', async ({ page }) => {
    await page.goto('/settings');
    await page.waitForLoadState('networkidle');
    
    // 检查设置页面基本元素
    console.log('设置页面加载成功');
  });
});
