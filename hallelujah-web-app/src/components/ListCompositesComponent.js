import React from 'react';
import ComponentRenderer from './ComponentRenderer';

const ListCompositesComponent = ({ name, param, value, onChange, description }) => {
  const handleAddItem = () => {
    const newValue = [...(value || []), {}];
    onChange(name, newValue);
  };

  const handleRemoveItem = (index) => {
    const newValue = [...value];
    newValue.splice(index, 1);
    onChange(name, newValue);
  };

  const handleItemChange = (index, itemName, itemValue) => {
    const newValue = [...value];
    newValue[index] = { ...newValue[index], [itemName]: itemValue };
    onChange(name, newValue);
  };

  return (
    <div>
      <h4>{name}</h4>
      {description && <p>{description}</p>}
      {(value || []).map((item, index) => (
        <div key={index} style={{ border: '1px solid #ccc', padding: '10px', margin: '5px' }}>
          {Object.keys(param).map(key => {
            if (key === 'type' || key === 'desc') return null;
            return (
              <ComponentRenderer
                key={key}
                name={key}
                param={param[key]}
                value={item[key]}
                onChange={(itemName, itemValue) => handleItemChange(index, itemName, itemValue)}
              />
            );
          })}
          <button type="button" onClick={() => handleRemoveItem(index)}>Remove</button>
        </div>
      ))}
      <button type="button" onClick={handleAddItem}>Add</button>
    </div>
  );
};

export default ListCompositesComponent;
