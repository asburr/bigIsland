import React, { useState, useEffect } from 'react';
import ComponentRenderer from './ComponentRenderer';
import './CommandEditor.css';

const CommandEditor = ({ commandName, commandData, onClose }) => {
  const [formData, setFormData] = useState({});

  useEffect(() => {
    // Initialize form data with default values from the schema
    const initialData = {};
    Object.keys(commandData).forEach(key => {
      if (key !== 'type' && key !== 'desc' && key !== 'eg') {
        initialData[key] = commandData[key].default;
      }
    });
    setFormData(initialData);
  }, [commandData]);

  const handleFormChange = (name, value) => {
    setFormData(prevData => ({
      ...prevData,
      [name]: value,
    }));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    console.log('Form data submitted:', formData);
    onClose();
  };

  return (
    <div className="modal-overlay">
      <div className="modal-content">
        <h2>Editing: {commandName}</h2>
        <p>{commandData.desc}</p>
        <form onSubmit={handleSubmit}>
          {Object.keys(commandData).map(key => {
            if (key === 'type' || key === 'desc' || key === 'eg') {
              return null;
            }
            return (
              <ComponentRenderer
                key={key}
                name={key}
                param={commandData[key]}
                value={formData[key]}
                onChange={handleFormChange}
              />
            );
          })}
          <button type="submit">Save</button>
          <button type="button" onClick={onClose}>Close</button>
        </form>
      </div>
    </div>
  );
};

export default CommandEditor;
