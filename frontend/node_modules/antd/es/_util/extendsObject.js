function mergeProps() {
  const ret = {};
  for (var _len = arguments.length, items = new Array(_len), _key = 0; _key < _len; _key++) {
    items[_key] = arguments[_key];
  }
  items.forEach(item => {
    if (item) {
      Object.keys(item).forEach(key => {
        if (item[key] !== undefined) {
          ret[key] = item[key];
        }
      });
    }
  });
  return ret;
}
export default mergeProps;