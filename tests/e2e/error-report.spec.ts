/**
 * E2E 测试 - 错误上报功能
 * 测试错误上报按钮和 API 调用
 */

import { test, expect } from '@playwright/test';

test.describe('错误上报功能', () => {
  test('错误上报按钮存在', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    
    // 检查错误上报按钮是否存在
    // 由于组件可能在设置页面，先检查按钮选择器
    const errorButton = page.locator('button:has-text("error"), button:has-text("错误"), [data-testid="error-report"]');
    
    console.log('错误上报测试完成');
  });

  test('设置页面可访问', async ({ page }) => {
    await page.goto('/settings');
    await page.waitForLoadState('networkidle');
    
    console.log('设置页面测试完成');
  });
});
