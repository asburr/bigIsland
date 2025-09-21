import React from 'react';

const IntComponent = ({ name, value, onChange, description }) => {
  return (
    <div>
      <label>{name}: </label>
      <input
        type="number"
        name={name}
        value={value}
        onChange={onChange}
      />
      {description && <p>{description}</p>}
    </div>
  );
};

export default IntComponent;
