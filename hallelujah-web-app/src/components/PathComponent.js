import React from 'react';

const PathComponent = ({ name, value, onChange, description }) => {
  return (
    <div>
      <label>{name}: </label>
      <input
        type="text"
        name={name}
        value={value}
        onChange={onChange}
      />
      {description && <p>{description}</p>}
    </div>
  );
};

export default PathComponent;
