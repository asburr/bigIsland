import React, { useState, useEffect } from 'react';
import CommandEditor from './components/CommandEditor';
import './App.css';

function App() {
  const [commands, setCommands] = useState(null);
  const [selectedCommand, setSelectedCommand] = useState(null);

  useEffect(() => {
    fetch('/worksheetHelp.json')
      .then(response => response.json())
      .then(data => {
        setCommands(data);
      })
      .catch(error => console.error('Error fetching worksheetHelp.json:', error));
  }, []);

  const handleCommandClick = (commandName) => {
    setSelectedCommand(commandName);
  };

  const handleCloseEditor = () => {
    setSelectedCommand(null);
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>Hallelujah Command Interface</h1>
      </header>
      <main>
        <h2>Available Commands</h2>
        {commands ? (
          <ul>
            {Object.keys(commands).map(commandName => (
              <li key={commandName} onClick={() => handleCommandClick(commandName)}>
                {commandName}
              </li>
            ))}
          </ul>
        ) : (
          <p>Loading commands...</p>
        )}
        {selectedCommand && (
          <CommandEditor
            commandName={selectedCommand}
            commandData={commands[selectedCommand]}
            onClose={handleCloseEditor}
          />
        )}
      </main>
    </div>
  );
}

export default App;
