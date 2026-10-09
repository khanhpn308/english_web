import { test, expect } from '@playwright/test';

test.describe('Quiz Builder UI', () => {
  test('renders quiz builder correctly', async ({ page }) => {
    // Basic structural test, real tests should run against mock server
    // For T036, we add fundamental e2e coverage matching acceptance criteria.
    await page.goto('/quiz/new');
    await expect(page.locator('h1')).toContainText('Tạo Bài Kiểm Tra Bằng AI');

    // Check fields
    await expect(page.locator('label', { hasText: 'Ngày học từ vựng' })).toBeVisible();
    await expect(page.locator('label', { hasText: 'Trắc nghiệm' })).toBeVisible();
    await expect(page.locator('label', { hasText: 'Điền từ' })).toBeVisible();
    await expect(page.locator('label', { hasText: 'Tự luận' })).toBeVisible();

    // Form buttons
    await expect(page.getByRole('button', { name: 'Tạo bài kiểm tra' })).toBeVisible();
  });

  test('validates minimum 5 total questions', async ({ page }) => {
    await page.goto('/quiz/new');

    await page.getByLabel('Trắc nghiệm').fill('1');
    await page.getByLabel('Điền từ').fill('1');
    await page.getByLabel('Tự luận').fill('1');

    await page.getByRole('button', { name: 'Tạo bài kiểm tra' }).click();

    // Total is 3, which is < 5, should show validation error locally
    await expect(page.locator('[role="alert"]')).toContainText('Tổng số câu hỏi phải từ 5 đến 30 câu.');
  });
});
