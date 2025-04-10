import re
from collections import deque
from typing import Any

import pytest
from dirty_equals import IsNonNegative, IsTuple

from pydantic_core import SchemaValidator, ValidationError, core_schema

from ..conftest import Err, PyAndJson, infinite_generator


@pytest.mark.parametrize(
    'variadic_item_index,items,input_value,expected',
    [
        (0, [{'type': 'int'}], [1, 2, 3], (1, 2, 3)),
        (0, [{'type': 'int'}], 1, Err('[type=tuple_type, input_value=1, input_type=int]')),
        (None, [{'type': 'int'}, {'type': 'int'}, {'type': 'int'}], [1, 2, '3'], (1, 2, 3)),
        (
            None,
            [{'type': 'int'}, {'type': 'int'}, {'type': 'int'}],
            5,
            Err('[type=tuple_type, input_value=5, input_type=int]'),
        ),
    ],
    ids=repr,
)
def test_tuple_json(py_and_json: PyAndJson, variadic_item_index, items, input_value, expected):
    v = py_and_json(core_schema.tuple_schema(items_schema=items, variadic_item_index=variadic_item_index))
    if isinstance(expected, Err):
        with pytest.raises(ValidationError, match=re.escape(expected.message)):
            v.validate_test(input_value)
    else:
        assert v.validate_test(input_value) == expected


def test_any_no_copy():
    v = SchemaValidator(core_schema.tuple_schema(items_schema=[core_schema.any_schema()], variadic_item_index=0))
    input_value = (1, '2', b'3')
    output = v.validate_python(input_value)
    assert output == input_value
    assert output is not input_value
    assert id(output) != id(input_value)


@pytest.mark.parametrize(
    'variadic_item_index,items,input_value,expected',
    [
        (0, [{'type': 'int'}], (1, 2, '33'), (1, 2, 33)),
        (0, [{'type': 'str'}], (b'1', b'2', '33'), ('1', '2', '33')),
        (None, [{'type': 'int'}, {'type': 'str'}, {'type': 'float'}], (1, b'a', 33), (1, 'a', 33.0)),
    ],
)
def test_tuple_strict_passes_with_tuple(variadic_item_index, items, input_value, expected):
    v = SchemaValidator(
        core_schema.tuple_schema(items_schema=items, variadic_item_index=variadic_item_index, strict=True)
    )
    assert v.validate_python(input_value) == expected


@pytest.mark.parametrize('fail_fast', [True, False])
def test_empty_positional_tuple(fail_fast):
    v = SchemaValidator(core_schema.tuple_schema(items_schema=[], fail_fast=fail_fast))
    assert v.validate_python(()) == ()
    assert v.validate_python([]) == ()
    with pytest.raises(ValidationError) as exc_info:
        v.validate_python((1,))

    # insert_assert(exc_info.value.errors(include_url=False))
    assert exc_info.value.errors(include_url=False) == [
        {
            'type': 'too_long',
            'loc': (),
            'msg': 'Tuple should have at most 0 items after validation, not 1',
            'input': (1,),
            'ctx': {'field_type': 'Tuple', 'max_length': 0, 'actual_length': 1},
        }
    ]


@pytest.mark.parametrize(
    'variadic_item_index,items', [(0, [{'type': 'int'}]), (None, [{'type': 'int'}, {'type': 'int'}, {'type': 'int'}])]
)
@pytest.mark.parametrize('wrong_coll_type', [list, set, frozenset])
def test_tuple_strict_fails_without_tuple(wrong_coll_type: type[Any], variadic_item_index, items):
    v = SchemaValidator(
        core_schema.tuple_schema(variadic_item_index=variadic_item_index, items_schema=items, strict=True)
    )
    with pytest.raises(ValidationError) as exc_info:
        v.validate_python(wrong_coll_type([1, 2, '33']))
    assert exc_info.value.errors(include_url=False) == [
        {
            'type': 'tuple_type',
            'loc': (),
            'msg': 'Input should be a valid tuple',
            'input': wrong_coll_type([1, 2, '33']),
        }
    ]


@pytest.mark.parametrize(
    'kwargs,input_value,expected',
    [
        ({}, (1, 2, 3, 4), (1, 2, 3, 4)),
        ({'min_length': 3}, (1, 2, 3, 4), (1, 2, 3, 4)),
        ({'min_length': 3}, (1, 2), Err('Tuple should have at least 3 items after validation, not 2 [type=too_short,')),
        ({'max_length': 4}, (1, 2, 3, 4), (1, 2, 3, 4)),
        (
            {'max_length': 3},
            (1, 2, 3, 4),
            Err('Tuple should have at most 3 items after validation, not 4 [type=too_long,'),
        ),
        (
            {'max_length': 3},
            [1, 2, 3, 4, 5],
            Err('Tuple should have at most 3 items after validation, not 5 [type=too_long,'),
        ),
        (
            {'max_length': 3},
            infinite_generator(),
            Err('Tuple should have at most 3 items after validation, not more [type=too_long,'),
        ),
    ],
    ids=repr,
)
def test_tuple_var_len_kwargs(kwargs: dict[str, Any], input_value, expected):
    v = SchemaValidator(
        core_schema.tuple_schema(items_schema=[core_schema.any_schema()], variadic_item_index=0, **kwargs)
    )
    if isinstance(expected, Err):
        with pytest.raises(ValidationError, match=re.escape(expected.message)):
            v.validate_python(input_value)
    else:
        assert v.validate_python(input_value) == expected


@pytest.mark.parametrize(
    'variadic_item_index,items', [(0, [{'type': 'int'}]), (None, [{'type': 'int'}, {'type': 'int'}, {'type': 'int'}])]
)
@pytest.mark.parametrize(
    'input_value,expected',
    [
        ((1, 2, '3'), (1, 2, 3)),
        ([1, 2, '3'], (1, 2, 3)),
        (deque((1, 2, '3')), (1, 2, 3)),
        ({1: 10, 2: 20, '3': '30'}.keys(), (1, 2, 3)),
        ({1: 10, 2: 20, '3': '30'}.values(), (10, 20, 30)),
        ({1: 10, 2: 20, '3': '30'}, Err('Input should be a valid tuple [type=tuple_type,')),
        ({1, 2, '3'}, IsTuple(1, 2, 3, check_order=False)),
        (frozenset([1, 2, '3']), IsTuple(1, 2, 3, check_order=False)),
    ],
    ids=repr,
)
def test_tuple_validate(input_value, expected, variadic_item_index, items):
    v = SchemaValidator(core_schema.tuple_schema(items_schema=items, variadic_item_index=variadic_item_index))
    if isinstance(expected, Err):
        with pytest.raises(ValidationError, match=re.escape(expected.message)):
            v.validate_python(input_value)
    else:
        assert v.validate_python(input_value) == expected


# Since `test_tuple_validate` is parametrized above, the generator is consumed
# on the first test run. This is a workaround to make sure the generator is
# always recreated.
@pytest.mark.parametrize(
    'variadic_item_index,items', [(0, [{'type': 'int'}]), (None, [{'type': 'int'}, {'type': 'int'}, {'type': 'int'}])]
)
def test_tuple_validate_iterator(variadic_item_index, items):
    v = SchemaValidator(core_schema.tuple_schema(items_schema=items, variadic_item_index=variadic_item_index))
    assert v.validate_python(x for x in [1, 2, '3']) == (1, 2, 3)


@pytest.mark.parametrize(
    'input_value,index',
    [
        (['wrong'], 0),
        (('wrong',), 0),
        ((1, 2, 3, 'wrong'), 3),
        ((1, 2, 3, 'wrong', 4), 3),
        ((1, 2, 'wrong'), IsNonNegative()),
    ],
)
def test_tuple_var_len_errors(input_value, index):
    v = SchemaValidator(core_schema.tuple_schema(items_schema=[core_schema.int_schema()], variadic_item_index=0))
    with pytest.raises(ValidationError) as exc_info:
        assert v.validate_python(input_value)
    assert exc_info.value.errors(include_url=False) == [
        {
            'type': 'int_parsing',
            'loc': (index,),
            'msg': 'Input should be a valid integer, unable to parse string as an integer',
            'input': 'wrong',
        }
    ]


@pytest.mark.parametrize(
    'input_value,items,index',
    [
        (['wrong'], [{'type': 'int'}], 0),
        (('wrong',), [{'type': 'int'}], 0),
        ((1, 2, 3, 'wrong'), [{'type': 'int'}, {'type': 'int'}, {'type': 'int'}, {'type': 'int'}], 3),
        (
            (1, 2, 3, 'wrong', 4),
            [{'type': 'int'}, {'type': 'int'}, {'type': 'int'}, {'type': 'int'}, {'type': 'int'}],
            3,
        ),
        ((1, 2, 'wrong'), [{'type': 'int'}, {'type': 'int'}, {'type': 'int'}], IsNonNegative()),
    ],
)
def test_tuple_fix_len_errors(input_value, items, index):
    v = SchemaValidator(core_schema.tuple_schema(items_schema=items))
    with pytest.raises(ValidationError) as exc_info:
        assert v.validate_python(input_value)
    assert exc_info.value.errors(include_url=False) == [
        {
            'type': 'int_parsing',
            'loc': (index,),
            'msg': 'Input should be a valid integer, unable to parse string as an integer',
            'input': 'wrong',
        }
    ]


def test_multiple_missing(py_and_json: PyAndJson):
    v = py_and_json(
        {'type': 'tuple', 'items_schema': [{'type': 'int'}, {'type': 'int'}, {'type': 'int'}, {'type': 'int'}]}
    )
    assert v.validate_test([1, 2, 3, 4]) == (1, 2, 3, 4)
    with pytest.raises(ValidationError) as exc_info:
        v.validate_test([1])
    assert exc_info.value.errors(include_url=False) == [
        {'type': 'missing', 'loc': (1,), 'msg': 'Field required', 'input': [1]},
        {'type': 'missing', 'loc': (2,), 'msg': 'Field required', 'input': [1]},
        {'type': 'missing', 'loc': (3,), 'msg': 'Field required', 'input': [1]},
    ]
    with pytest.raises(ValidationError) as exc_info:
        v.validate_test([1, 2, 3])
    assert exc_info.value.errors(include_url=False) == [
        {'type': 'missing', 'loc': (3,), 'msg': 'Field required', 'input': [1, 2, 3]}
    ]


def test_extra_arguments(py_and_json: PyAndJson):
    v = py_and_json({'type': 'tuple', 'items_schema': [{'type': 'int'}, {'type': 'int'}]})
    assert v.validate_test([1, 2]) == (1, 2)
    with pytest.raises(ValidationError) as exc_info:
        v.validate_test([1, 2, 3, 4])
    # insert_assert(exc_info.value.errors(include_url=False))
    assert exc_info.value.errors(include_url=False) == [
        {
            'type': 'too_long',
            'loc': (),
            'msg': 'Tuple should have at most 2 items after validation, not 4',
            'input': [1, 2, 3, 4],
            'ctx': {'field_type': 'Tuple', 'max_length': 2, 'actual_length': 4},
        }
    ]


def test_positional_empty(py_and_json: PyAndJson):
    v = py_and_json({'type': 'tuple', 'items_schema': []})
    assert v.validate_test([]) == ()
    assert v.validate_python(()) == ()
    with pytest.raises(ValidationError, match='type=too_long,'):
        v.validate_test([1])


def test_positional_empty_extra(py_and_json: PyAndJson):
    v = py_and_json({'type': 'tuple', 'items_schema': [{'type': 'int'}], 'variadic_item_index': 0})
    assert v.validate_test([]) == ()
    assert v.validate_python(()) == ()
    assert v.validate_test([1]) == (1,)
    assert v.validate_test(list(range(100))) == tuple(range(100))


@pytest.mark.parametrize('input_value,expected', [((1, 2, 3), (1, 2, 3)), ([1, 2, 3], [1, 2, 3])])
def test_union_tuple_list(input_value, expected):
    v = SchemaValidator(
        core_schema.union_schema(
            choices=[
                core_schema.tuple_schema(items_schema=[core_schema.any_schema()], variadic_item_index=0),
                core_schema.list_schema(),
            ]
        )
    )
    assert v.validate_python(input_value) == expected


@pytest.mark.parametrize(
    'input_value,expected',
    [
        ((1, 2, 3), (1, 2, 3)),
        (('a', 'b', 'c'), ('a', 'b', 'c')),
        (('a', b'a', 'c'), ('a', 'a', 'c')),
        (
            [5],
            Err(
                '2 validation errors for union',
                errors=[
                    {
                        # first of all, not a tuple of ints ..
                        'type': 'tuple_type',
                        'loc': ('tuple[int, ...]',),
                        'msg': 'Input should be a valid tuple',
                        'input': [5],
                    },
                    # .. and not a tuple of strings, either
                    {
                        'type': 'tuple_type',
                        'loc': ('tuple[str, ...]',),
                        'msg': 'Input should be a valid tuple',
                        'input': [5],
                    },
                ],
            ),
        ),
    ],
    ids=repr,
)
def test_union_tuple_var_len(input_value, expected):
    v = SchemaValidator(
        core_schema.union_schema(
            choices=[
                core_schema.tuple_schema(items_schema=[core_schema.int_schema()], variadic_item_index=0, strict=True),
                core_schema.tuple_schema(items_schema=[core_schema.str_schema()], variadic_item_index=0, strict=True),
            ]
        )
    )
    if isinstance(expected, Err):
        with pytest.raises(ValidationError, match=re.escape(expected.message)) as exc_info:
            v.validate_python(input_value)
        if expected.errors is not None:
            assert exc_info.value.errors(include_url=False) == expected.errors
    else:
        assert v.validate_python(input_value) == expected


@pytest.mark.parametrize(
    'input_value,expected',
    [
        ((1, 2, 3), (1, 2, 3)),
        (('a', 'b', 'c'), ('a', 'b', 'c')),
        (
            [5, '1', 1],
            Err(
                '2 validation errors for union',
                errors=[
                    {
                        'type': 'tuple_type',
                        'loc': ('tuple[int, int, int]',),
                        'msg': 'Input should be a valid tuple',
                        'input': [5, '1', 1],
                    },
                    {
                        'type': 'tuple_type',
                        'loc': ('tuple[str, str, str]',),
                        'msg': 'Input should be a valid tuple',
                        'input': [5, '1', 1],
                    },
                ],
            ),
        ),
    ],
    ids=repr,
)
def test_union_tuple_fix_len(input_value, expected):
    v = SchemaValidator(
        core_schema.union_schema(
            choices=[
                core_schema.tuple_schema(
                    items_schema=[core_schema.int_schema(), core_schema.int_schema(), core_schema.int_schema()],
                    strict=True,
                ),
                core_schema.tuple_schema(
                    items_schema=[core_schema.str_schema(), core_schema.str_schema(), core_schema.str_schema()],
                    strict=True,
                ),
            ]
        )
    )
    if isinstance(expected, Err):
        with pytest.raises(ValidationError, match=re.escape(expected.message)) as exc_info:
            v.validate_python(input_value)
        if expected.errors is not None:
            assert exc_info.value.errors(include_url=False) == expected.errors
    else:
        assert v.validate_python(input_value) == expected


def test_tuple_fix_error():
    v = SchemaValidator(core_schema.tuple_schema(items_schema=[core_schema.int_schema(), core_schema.str_schema()]))
    with pytest.raises(ValidationError) as exc_info:
        v.validate_python([1])

    assert exc_info.value.errors(include_url=False) == [
        {'type': 'missing', 'loc': (1,), 'msg': 'Field required', 'input': [1]}
    ]


@pytest.mark.parametrize(
    'input_value,expected',
    [
        ([1, 'a'], (1, 'a')),
        ((1, 'a'), (1, 'a')),
        ((1, 'a', 'b'), (1, 'a', 'b')),
        ([1, 'a', 'b', 'c', 'd'], (1, 'a', 'b', 'c', 'd')),
        (deque([1, 'a', 'b', 'c', 'd']), (1, 'a', 'b', 'c', 'd')),
        ([1], Err('type=missing', errors=[{'type': 'missing', 'loc': (1,), 'msg': 'Field required', 'input': [1]}])),
    ],
)
def test_tuple_fix_extra(input_value, expected):
    v = SchemaValidator(
        core_schema.tuple_schema(
            items_schema=[core_schema.int_schema(), core_schema.str_schema(), core_schema.str_schema()],
            variadic_item_index=2,
        )
    )

    if isinstance(expected, Err):
        with pytest.raises(ValidationError, match=re.escape(expected.message)) as exc_info:
            v.validate_python(input_value)
        assert exc_info.value.errors(include_url=False) == expected.errors
    else:
        assert v.validate_python(input_value) == expected


def test_tuple_fix_extra_any():
    v = SchemaValidator(
        core_schema.tuple_schema(
            items_schema=[core_schema.str_schema(), core_schema.any_schema()], variadic_item_index=1
        )
    )
    assert v.validate_python([b'1']) == ('1',)
    assert v.validate_python([b'1', 2]) == ('1', 2)
    assert v.validate_python((b'1', 2)) == ('1', 2)
    assert v.validate_python([b'1', 2, b'3']) == ('1', 2, b'3')
    with pytest.raises(ValidationError) as exc_info:
        v.validate_python([])
    assert exc_info.value.errors(include_url=False) == [
        {'type': 'missing', 'loc': (0,), 'msg': 'Field required', 'input': []}
    ]


def test_generator_error():
    def gen(error: bool):
        yield 1
        yield 2
        if error:
            raise RuntimeError('error')
        yield 3

    v = SchemaValidator(core_schema.tuple_schema(items_schema=[core_schema.int_schema()], variadic_item_index=0))
    assert v.validate_python(gen(False)) == (1, 2, 3)

    msg = r'Error iterating over object, error: RuntimeError: error \[type=iteration_error,'
    with pytest.raises(ValidationError, match=msg):
        v.validate_python(gen(True))


@pytest.mark.parametrize(
    'input_value,items_schema,expected',
    [
        pytest.param(
            {1: 10, 2: 20, '3': '30'}.items(),
            {'type': 'tuple', 'items_schema': [{'type': 'any'}], 'variadic_item_index': 0},
            ((1, 10), (2, 20), ('3', '30')),
            id='Tuple[Any, Any]',
        ),
        pytest.param(
            {1: 10, 2: 20, '3': '30'}.items(),
            {'type': 'tuple', 'items_schema': [{'type': 'int'}], 'variadic_item_index': 0},
            ((1, 10), (2, 20), (3, 30)),
            id='Tuple[int, int]',
        ),
        pytest.param({1: 10, 2: 20, '3': '30'}.items(), {'type': 'any'}, ((1, 10), (2, 20), ('3', '30')), id='Any'),
    ],
)
def test_frozenset_from_dict_items(input_value, items_schema, expected):
    v = SchemaValidator(core_schema.tuple_schema(items_schema=[items_schema], variadic_item_index=0))
    output = v.validate_python(input_value)
    assert isinstance(output, tuple)
    assert output == expected


@pytest.mark.parametrize(
    'input_value,expected',
    [
        ([1, 2, 3, 4], (1, 2, 3, 4)),
        ([1, 2, 3, 4, 5], Err('Tuple should have at most 4 items after validation, not 5 [type=too_long,')),
        ([1, 2, 3, 'x', 4], (1, 2, 3, 4)),
    ],
)
def test_length_constraints_omit(input_value, expected):
    v = SchemaValidator(
        core_schema.tuple_schema(
            items_schema=[core_schema.with_default_schema(schema=core_schema.int_schema(), on_error='omit')],
            variadic_item_index=0,
            max_length=4,
        )
    )
    if isinstance(expected, Err):
        with pytest.raises(ValidationError, match=re.escape(expected.message)):
            v.validate_python(input_value)
    else:
        assert v.validate_python(input_value) == expected


@pytest.mark.parametrize(
    'fail_fast,expected',
    [
        pytest.param(
            True,
            [
                {
                    'type': 'int_parsing',
                    'loc': (1,),
                    'msg': 'Input should be a valid integer, unable to parse string as an integer',
                    'input': 'not-num',
                }
            ],
            id='fail_fast',
        ),
        pytest.param(
            False,
            [
                {
                    'type': 'int_parsing',
                    'loc': (1,),
                    'msg': 'Input should be a valid integer, unable to parse string as an integer',
                    'input': 'not-num',
                },
                {
                    'type': 'float_parsing',
                    'loc': (2,),
                    'msg': 'Input should be a valid number, unable to parse string as a number',
                    'input': 'again',
                },
            ],
            id='not_fail_fast',
        ),
    ],
)
def test_tuple_fail_fast(fail_fast, expected):
    s = core_schema.tuple_schema(
        [
            core_schema.str_schema(),
            core_schema.int_schema(),
            core_schema.float_schema(),
        ],
        variadic_item_index=None,
        fail_fast=fail_fast,
    )
    v = SchemaValidator(s)

    with pytest.raises(ValidationError) as exc_info:
        v.validate_python(['str', 'not-num', 'again'])

    assert exc_info.value.errors(include_url=False) == expected
