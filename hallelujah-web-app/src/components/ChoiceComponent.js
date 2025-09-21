import React from 'react';
import ComponentRenderer from './ComponentRenderer';

const ChoiceComponent = ({ name, param, value, onChange, description }) => {
  const choices = param.choice;
  const isArrayOfStrings = Array.isArray(choices);

  if (isArrayOfStrings) {
    return (
      <div>
        <label>{name}: </label>
        <select name={name} value={value} onChange={(e) => onChange(name, e.target.value)}>
          {choices.map(choice => (
            <option key={choice} value={choice}>{choice}</option>
          ))}
        </select>
        {description && <p>{description}</p>}
      </div>
    );
  } else {
    // It's an object with nested parameters
    return (
      <div>
        <h4>{name}</h4>
        {description && <p>{description}</p>}
        <select name={name} value={value && value.selected} onChange={(e) => {
          const selectedKey = e.target.value;
          const newValue = { selected: selectedKey, ...param[selectedKey] };
          onChange(name, newValue);
        }}>
          {Object.keys(choices).map(key => (
            <option key={key} value={key}>{key}</option>
          ))}
        </select>
        {value && value.selected &&
          <ComponentRenderer
            name={value.selected}
            param={choices[value.selected]}
            value={value}
            onChange={(childName, childValue) => {
              const newValue = { ...value, [childName]: childValue };
              onChange(name, newValue);
            }}
          />
        }
      </div>
    );
  }
};

export default ChoiceComponent;
