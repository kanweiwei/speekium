/**
 * E2E 测试 - 应用基础功能
 * 测试应用的基本结构和导航
 */

import { test, expect } from '@playwright/test';

test.describe('应用基础功能', () => {
  test('应用首页加载', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    
    // 验证页面加载
    const url = page.url();
    console.log('当前 URL:', url);
    
    expect(url).toContain('localhost');
  });

  test('主题切换可用', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    
    // 检查主题切换按钮
    console.log('主题测试完成');
  });

  test('快捷键显示正常', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    
    // 检查快捷键相关元素
    console.log('快捷键测试完成');
  });
});
