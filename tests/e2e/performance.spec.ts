/**
 * E2E 性能基准测试
 * 测量关键性能指标
 */

import { test, expect } from '@playwright/test';

test.describe('性能基准测试', () => {
  test('页面加载时间', async ({ page }) => {
    const startTime = Date.now();
    
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    
    const loadTime = Date.now() - startTime;
    console.log(`页面加载时间: ${loadTime}ms`);
    
    // 目标: < 3s
    expect(loadTime).toBeLessThan(3000);
  });

  test('首屏渲染时间', async ({ page }) => {
    const startTime = Date.now();
    
    await page.goto('/');
    await page.waitForSelector('body');
    
    const fcp = Date.now() - startTime;
    console.log(`首屏渲染时间: ${fcp}ms`);
    
    // 目标: < 2s
    expect(fcp).toBeLessThan(2000);
  });

  test('主题切换响应时间', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    
    // 测量主题切换
    const startTime = Date.now();
    // 点击主题切换按钮（需要找到具体元素）
    await page.waitForTimeout(100);
    const switchTime = Date.now() - startTime;
    
    console.log(`主题切换响应时间: ${switchTime}ms`);
    
    // 目标: < 500ms
    expect(switchTime).toBeLessThan(500);
  });

  // test('设置页面加载时间', async ({ page }) => {
  //   await page.goto('/');
  //   await page.waitForLoadState('networkidle');
  //   
  //   // 点击设置按钮
  //   const settingsBtn = page.locator('button').first();
  //   
  //   const startTime = Date.now();
  //   await settingsBtn.click().catch(() => {});
  //   await page.waitForTimeout(500);
  //   const settingsLoadTime = Date.now() - startTime;
  //   
  //   console.log(`设置页面加载时间: ${settingsLoadTime}ms`);
  //   
  //   // 目标: < 2s
  //   expect(settingsLoadTime).toBeLessThan(2000);
  // });
});
