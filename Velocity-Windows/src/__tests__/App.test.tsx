import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import App from '../App';

describe('App', () => {
    it('renders without crashing', () => {
        render(<App />);
        // Check that the main container exists
        expect(document.querySelector('.app-container')).toBeInTheDocument();
    });

    it('shows Velocity logo text', () => {
        render(<App />);
        const velocityElements = screen.getAllByText('Velocity');
        expect(velocityElements.length).toBeGreaterThan(0);
    });
});
