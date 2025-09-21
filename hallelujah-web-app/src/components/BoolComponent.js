import React from 'react';

const BoolComponent = ({ name, value, onChange, description }) => {
  return (
    <div>
      <label>
        <input
          type="checkbox"
          name={name}
          checked={value}
          onChange={onChange}
        />
        {name}
      </label>
      {description && <p>{description}</p>}
    </div>
  );
};

export default BoolComponent;
