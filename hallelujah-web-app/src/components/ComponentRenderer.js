import React from 'react';
import StringComponent from './StringComponent';
import IntComponent from './IntComponent';
import BoolComponent from './BoolComponent';
import PathComponent from './PathComponent';
import ChoiceComponent from './ChoiceComponent';
import ListCompositesComponent from './ListCompositesComponent';

const ComponentRenderer = ({ name, param, value, onChange }) => {
  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    const newValue = type === 'checkbox' ? checked : value;
    onChange(name, newValue);
  };

  switch (param.type) {
    case 'str':
      return <StringComponent name={name} value={value} onChange={handleChange} description={param.desc} />;
    case 'int':
      return <IntComponent name={name} value={value} onChange={handleChange} description={param.desc} />;
    case 'bool':
      return <BoolComponent name={name} value={value} onChange={handleChange} description={param.desc} />;
    case 'path':
      return <PathComponent name={name} value={value} onChange={handleChange} description={param.desc} />;
    case 'choice':
      return <ChoiceComponent name={name} param={param} value={value} onChange={onChange} description={param.desc} />;
    case 'listComposites':
      return <ListCompositesComponent name={name} param={param} value={value} onChange={onChange} description={param.desc} />;
    case 'composite':
      return (
        <div>
          <h3>{name}</h3>
          {param.desc && <p>{param.desc}</p>}
          {Object.keys(param).map(key => {
            if (key === 'type' || key === 'desc') {
              return null;
            }
            return (
              <ComponentRenderer
                key={key}
                name={key}
                param={param[key]}
                value={value && value[key]}
                onChange={(childName, childValue) => {
                  const newValue = { ...value, [childName]: childValue };
                  onChange(name, newValue);
                }}
              />
            );
          })}
        </div>
      );
    default:
      return <p>Unsupported type: {param.type}</p>;
  }
};

export default ComponentRenderer;
