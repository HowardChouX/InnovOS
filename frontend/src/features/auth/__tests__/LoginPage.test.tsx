import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { describe, it, expect } from 'vitest';
import { LoginPage } from '../LoginPage';

function renderWithRouter(ui: React.ReactElement) {
  return render(<BrowserRouter>{ui}</BrowserRouter>);
}

describe('LoginPage', () => {
  it('renders InnovOS branding', () => {
    renderWithRouter(<LoginPage />);
    expect(screen.getByText('InnovOS')).toBeInTheDocument();
    expect(screen.getByText('创新智能操作系统')).toBeInTheDocument();
  });

  it('renders login form with username input', () => {
    renderWithRouter(<LoginPage />);
    const usernameInput = screen.getByPlaceholderText('输入用户名');
    expect(usernameInput).toBeInTheDocument();
    expect(usernameInput).toHaveAttribute('placeholder', '输入用户名');
  });

  it('renders login form with password input', () => {
    renderWithRouter(<LoginPage />);
    const passwordInput = screen.getByPlaceholderText('输入密码');
    expect(passwordInput).toBeInTheDocument();
    expect(passwordInput).toHaveAttribute('type', 'password');
  });

  it('renders submit button', () => {
    renderWithRouter(<LoginPage />);
    const submitButton = screen.getByRole('button', { name: '登录' });
    expect(submitButton).toBeInTheDocument();
  });

  it('renders register link', () => {
    renderWithRouter(<LoginPage />);
    const registerLink = screen.getByText('注册');
    expect(registerLink).toBeInTheDocument();
    expect(registerLink).toHaveAttribute('href', '/register');
  });
});
