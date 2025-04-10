use pyo3::types::PyDict;
use pyo3::{prelude::*, IntoPyObjectExt};

use crate::build_tools::is_strict;
use crate::errors::ValResult;
use crate::input::Input;

use super::{BuildValidator, CombinedValidator, DefinitionsBuilder, ValidationState, Validator};

#[derive(Debug, Clone)]
pub struct BoolValidator {
    strict: bool,
}

impl BuildValidator for BoolValidator {
    const EXPECTED_TYPE: &'static str = "bool";

    fn build(
        schema: &Bound<'_, PyDict>,
        config: Option<&Bound<'_, PyDict>>,
        _definitions: &mut DefinitionsBuilder<CombinedValidator>,
    ) -> PyResult<CombinedValidator> {
        Ok(Self {
            strict: is_strict(schema, config)?,
        }
        .into())
    }
}

impl_py_gc_traverse!(BoolValidator {});

impl Validator for BoolValidator {
    fn validate<'py>(
        &self,
        py: Python<'py>,
        input: &(impl Input<'py> + ?Sized),
        state: &mut ValidationState<'_, 'py>,
    ) -> ValResult<PyObject> {
        // TODO in theory this could be quicker if we used PyBool rather than going to a bool
        // and back again, might be worth profiling?
        input
            .validate_bool(state.strict_or(self.strict))
            .and_then(|val_match| Ok(val_match.unpack(state).into_py_any(py)?))
    }

    fn get_name(&self) -> &str {
        Self::EXPECTED_TYPE
    }
}
