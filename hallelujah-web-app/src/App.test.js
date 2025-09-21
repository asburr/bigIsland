import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import App from './App';

// Mock the fetch function
global.fetch = jest.fn(() =>
  Promise.resolve({
    json: () => Promise.resolve({
      "test": {
        "type": "composite",
        "desc": "This comment returns the string:testing"
      }
    }),
  })
);

test('renders the command list and opens the editor on click', async () => {
  render(<App />);

  // Wait for the commands to be loaded and displayed
  const commandElement = await waitFor(() => screen.getByText(/test/i));
  expect(commandElement).toBeInTheDocument();

  // Click on the command
  fireEvent.click(commandElement);

  // Wait for the editor to appear
  const editorTitle = await waitFor(() => screen.getByText(/Editing: test/i));
  expect(editorTitle).toBeInTheDocument();
});
